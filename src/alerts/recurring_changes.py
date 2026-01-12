"""Recurring transaction change detection."""

from datetime import date, timedelta
from typing import Optional

from src.alerts.base import AlertDetector, Alert, AlertType, AlertSeverity, AlertRegistry
from src.utils.formatters import milliunits_to_dollars


class RecurringChangeDetector(AlertDetector):
    """
    Detects changes in recurring/scheduled transactions:

    1. Amount changes - when a recurring transaction posts with a different amount
    2. Missing transactions - when an expected recurring doesn't appear

    Uses scheduled_transactions as the baseline and compares against
    actual posted transactions.
    """

    DEFAULT_CONFIG = {
        "amount_tolerance_percent": 5.0,
        "amount_tolerance_absolute": 100,  # milliunits ($0.10)
        "days_overdue_warning": 3,
        "days_overdue_critical": 7,
        "lookback_days": 60,
    }

    def __init__(self, db, config: Optional[dict] = None):
        super().__init__(db, config)
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    @property
    def alert_type(self) -> AlertType:
        return AlertType.RECURRING_CHANGE

    def detect(self, budget_id: str) -> list[Alert]:
        """
        Detect changes in recurring transactions.
        """
        alerts = []

        # Get all active scheduled transactions
        scheduled = self.db.get_scheduled_transactions(budget_id)

        for sched in scheduled:
            if sched['deleted']:
                continue

            # Check for amount changes in recent posts
            amount_alert = self._check_amount_change(budget_id, sched)
            if amount_alert:
                alerts.append(amount_alert)

            # Check for missing expected transactions
            missing_alert = self._check_missing(budget_id, sched)
            if missing_alert:
                alerts.append(missing_alert)

        return alerts

    def _check_amount_change(self, budget_id: str, sched) -> Optional[Alert]:
        """Check if recent transactions for this recurring have different amounts."""
        if not sched['payee_id']:
            return None

        # Find matching transactions by payee in recent period
        recent_matches = self.db.get_transactions_by_payee(
            budget_id=budget_id,
            payee_id=sched['payee_id'],
            days=self.config["lookback_days"]
        )

        if not recent_matches:
            return None

        expected = abs(sched['amount'])
        tolerance_pct = self.config["amount_tolerance_percent"] / 100
        tolerance_abs = self.config["amount_tolerance_absolute"]

        for txn in recent_matches:
            actual = abs(txn['amount'])
            diff = abs(actual - expected)

            # Calculate percentage difference
            if expected > 0:
                diff_pct = diff / expected
            else:
                diff_pct = 0

            # Check if outside tolerance (both conditions must be exceeded)
            if diff > tolerance_abs and diff_pct > tolerance_pct:
                return self._create_amount_change_alert(sched, txn, expected, actual, diff)

        return None

    def _check_missing(self, budget_id: str, sched) -> Optional[Alert]:
        """Check if a scheduled transaction is overdue."""
        today = date.today()

        # Parse date_next
        if isinstance(sched['date_next'], str):
            expected_date = date.fromisoformat(sched['date_next'])
        else:
            expected_date = sched['date_next']

        if expected_date > today:
            # Not due yet
            return None

        days_overdue = (today - expected_date).days

        if days_overdue < self.config["days_overdue_warning"]:
            return None

        # Check if transaction actually posted
        if sched['payee_id']:
            posted = self.db.find_matching_transaction(
                budget_id=budget_id,
                payee_id=sched['payee_id'],
                date_start=expected_date - timedelta(days=5),
                date_end=today,
                amount=sched['amount'],
                tolerance=self.config["amount_tolerance_absolute"]
            )

            if posted:
                return None  # Found it, not missing

        severity = (
            AlertSeverity.CRITICAL
            if days_overdue >= self.config["days_overdue_critical"]
            else AlertSeverity.WARNING
        )

        return self._create_missing_alert(sched, expected_date, days_overdue, severity)

    def _create_amount_change_alert(self, sched, txn, expected: int, actual: int, diff: int) -> Alert:
        """Create alert for recurring amount change."""
        expected_dollars = milliunits_to_dollars(expected)
        actual_dollars = milliunits_to_dollars(actual)
        diff_dollars = milliunits_to_dollars(diff)
        payee = sched['payee_name'] or "Unknown"

        direction = "increased" if actual > expected else "decreased"

        return Alert(
            alert_type=AlertType.RECURRING_CHANGE,
            severity=AlertSeverity.WARNING,
            title=f"Recurring amount changed: {payee}",
            description=(
                f"Expected ${expected_dollars:,.2f}, charged ${actual_dollars:,.2f}. "
                f"Amount {direction} by ${diff_dollars:,.2f}."
            ),
            related_entity_id=sched['id'],
            related_entity_type="scheduled_transaction",
            metadata={
                "scheduled_id": sched['id'],
                "transaction_id": txn['id'],
                "expected_amount": expected,
                "actual_amount": actual,
                "difference": diff,
                "payee": payee,
                "transaction_date": txn['date']
            }
        )

    def _create_missing_alert(self, sched, expected_date: date, days_overdue: int,
                               severity: AlertSeverity) -> Alert:
        """Create alert for missing recurring transaction."""
        payee = sched['payee_name'] or "Unknown"
        expected_dollars = milliunits_to_dollars(abs(sched['amount']))

        return Alert(
            alert_type=AlertType.RECURRING_MISSING,
            severity=severity,
            title=f"Missing recurring: {payee}",
            description=(
                f"Expected ${expected_dollars:,.2f} on {expected_date.strftime('%b %d')}, "
                f"now {days_overdue} days overdue."
            ),
            related_entity_id=sched['id'],
            related_entity_type="scheduled_transaction",
            metadata={
                "scheduled_id": sched['id'],
                "expected_date": str(expected_date),
                "days_overdue": days_overdue,
                "payee": payee,
                "expected_amount": sched['amount'],
                "frequency": sched['frequency']
            }
        )

    def get_config_schema(self) -> dict:
        """Return configuration schema for this detector."""
        return {
            "amount_tolerance_percent": {
                "type": "float",
                "default": 5.0,
                "min": 0,
                "max": 20,
                "description": "Percentage variance allowed before alerting"
            },
            "amount_tolerance_absolute": {
                "type": "int",
                "default": 100,
                "min": 0,
                "max": 10000,
                "description": "Absolute variance in milliunits allowed"
            },
            "days_overdue_warning": {
                "type": "int",
                "default": 3,
                "min": 1,
                "max": 14,
                "description": "Days past due before warning"
            },
            "days_overdue_critical": {
                "type": "int",
                "default": 7,
                "min": 3,
                "max": 30,
                "description": "Days past due before critical alert"
            },
            "lookback_days": {
                "type": "int",
                "default": 60,
                "min": 30,
                "max": 180,
                "description": "Days to look back for amount comparison"
            }
        }


# Register the detector
AlertRegistry.register(RecurringChangeDetector)
