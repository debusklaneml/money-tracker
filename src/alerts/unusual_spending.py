"""Unusual spending detection using Modified Z-Score algorithm."""

import numpy as np
from typing import Optional

from src.alerts.base import AlertDetector, Alert, AlertType, AlertSeverity, AlertRegistry
from src.utils.formatters import milliunits_to_dollars


class UnusualSpendingDetector(AlertDetector):
    """
    Detects unusual spending using Modified Z-Score.

    Modified Z-Score = 0.6745 * (x - median) / MAD
    where MAD = median(|x - median|)

    This is more robust than standard Z-Score because it uses
    median instead of mean, making it resistant to existing outliers.

    Thresholds:
    - |MZ| > 2.5: Warning (unusual)
    - |MZ| > 3.5: Critical (highly unusual)
    """

    DEFAULT_CONFIG = {
        "warning_threshold": 2.5,
        "critical_threshold": 3.5,
        "min_history_transactions": 5,
        "lookback_months": 6,
        "recent_days": 30,
    }

    def __init__(self, db, config: Optional[dict] = None):
        super().__init__(db, config)
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    @property
    def alert_type(self) -> AlertType:
        return AlertType.UNUSUAL_SPENDING

    def _calculate_modified_zscore(self, historical_values: np.ndarray, new_value: float) -> float:
        """
        Calculate Modified Z-Score for a new value against historical values.

        Args:
            historical_values: Array of historical transaction amounts
            new_value: The new transaction amount to evaluate

        Returns:
            Modified Z-Score (0 if insufficient data)
        """
        if len(historical_values) < 2:
            return 0.0

        median = np.median(historical_values)
        mad = np.median(np.abs(historical_values - median))

        if mad == 0:
            # All historical values identical, use standard deviation fallback
            std = np.std(historical_values)
            if std == 0:
                return 0.0
            return (new_value - median) / std

        # 0.6745 is the constant factor to make MAD comparable to standard deviation
        # for normally distributed data
        return 0.6745 * (new_value - median) / mad

    def detect(self, budget_id: str) -> list[Alert]:
        """
        Detect unusual spending in recent transactions.

        Compares each recent transaction against historical transactions
        in the same category to identify outliers.
        """
        alerts = []

        # Get recent transactions
        recent_txns = self.db.get_recent_transactions(
            budget_id,
            days=self.config["recent_days"]
        )

        for txn in recent_txns:
            # Skip transactions without a category
            if not txn['category_id']:
                continue

            # Skip inflows (positive amounts)
            if txn['amount'] >= 0:
                continue

            # Get historical transactions for same category
            historical = self.db.get_category_transactions(
                budget_id=budget_id,
                category_id=txn['category_id'],
                months=self.config["lookback_months"],
                exclude_id=txn['id']
            )

            # Need minimum history for comparison
            if len(historical) < self.config["min_history_transactions"]:
                continue

            # Calculate amounts (use absolute values for outflows)
            hist_amounts = np.array([abs(t['amount']) for t in historical])
            txn_amount = abs(txn['amount'])

            mz_score = self._calculate_modified_zscore(hist_amounts, txn_amount)

            # Check thresholds
            if abs(mz_score) > self.config["critical_threshold"]:
                alerts.append(self._create_alert(txn, mz_score, AlertSeverity.CRITICAL, hist_amounts))
            elif abs(mz_score) > self.config["warning_threshold"]:
                alerts.append(self._create_alert(txn, mz_score, AlertSeverity.WARNING, hist_amounts))

        return alerts

    def _create_alert(self, txn, mz_score: float, severity: AlertSeverity,
                      hist_amounts: np.ndarray) -> Alert:
        """Create an alert for an unusual transaction."""
        amount = milliunits_to_dollars(abs(txn['amount']))
        median_amount = milliunits_to_dollars(int(np.median(hist_amounts)))

        direction = "higher" if mz_score > 0 else "lower"
        payee = txn['payee_name'] or "Unknown"
        category = txn['category_name'] or "Uncategorized"

        return Alert(
            alert_type=AlertType.UNUSUAL_SPENDING,
            severity=severity,
            title=f"Unusual spending in {category}",
            description=(
                f"Transaction of ${amount:,.2f} at {payee} is significantly "
                f"{direction} than typical (median: ${median_amount:,.2f})."
            ),
            related_entity_id=txn['id'],
            related_entity_type="transaction",
            metadata={
                "amount": txn['amount'],
                "mz_score": round(mz_score, 2),
                "payee": payee,
                "category": category,
                "category_id": txn['category_id'],
                "date": txn['date'],
                "median_amount": int(np.median(hist_amounts)),
                "sample_size": len(hist_amounts)
            }
        )

    def get_config_schema(self) -> dict:
        """Return configuration schema for this detector."""
        return {
            "warning_threshold": {
                "type": "float",
                "default": 2.5,
                "min": 1.0,
                "max": 5.0,
                "description": "Modified Z-Score threshold for warning alerts"
            },
            "critical_threshold": {
                "type": "float",
                "default": 3.5,
                "min": 2.0,
                "max": 6.0,
                "description": "Modified Z-Score threshold for critical alerts"
            },
            "min_history_transactions": {
                "type": "int",
                "default": 5,
                "min": 3,
                "max": 20,
                "description": "Minimum historical transactions required for comparison"
            },
            "lookback_months": {
                "type": "int",
                "default": 6,
                "min": 1,
                "max": 24,
                "description": "How many months of history to analyze"
            },
            "recent_days": {
                "type": "int",
                "default": 30,
                "min": 7,
                "max": 90,
                "description": "Days to look back for recent transactions"
            }
        }


# Register the detector
AlertRegistry.register(UnusualSpendingDetector)
