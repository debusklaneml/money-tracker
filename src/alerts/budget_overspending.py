"""Budget overspending detection."""

from typing import Optional

from src.alerts.base import AlertDetector, Alert, AlertType, AlertSeverity, AlertRegistry
from src.utils.formatters import milliunits_to_dollars


class BudgetOverspendingDetector(AlertDetector):
    """
    Detects when category spending exceeds budgeted amounts.

    Thresholds:
    - 90% of budget: INFO (approaching limit)
    - 100% of budget: WARNING (at limit)
    - >100% of budget: CRITICAL (overspent)
    """

    DEFAULT_CONFIG = {
        "approaching_threshold": 0.90,
        "at_limit_threshold": 1.00,
        "ignore_zero_budget": True,
        "alert_zero_budget_spending": True,
    }

    def __init__(self, db, config: Optional[dict] = None):
        super().__init__(db, config)
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    @property
    def alert_type(self) -> AlertType:
        return AlertType.BUDGET_OVERSPENDING

    def detect(self, budget_id: str) -> list[Alert]:
        """
        Detect budget overspending in current month categories.
        """
        alerts = []

        # Get current month categories with budget data
        categories = self.db.get_current_month_categories(budget_id)

        for cat in categories:
            # Skip hidden categories
            if cat['hidden']:
                continue

            budgeted = cat['month_budgeted'] or cat['budgeted'] or 0
            activity = cat['month_activity'] or cat['activity'] or 0

            # Activity is negative for spending
            spent = abs(activity) if activity < 0 else 0

            if budgeted == 0:
                # No budget assigned
                if self.config["ignore_zero_budget"]:
                    continue

                # Alert on spending without budget
                if spent > 0 and self.config["alert_zero_budget_spending"]:
                    alerts.append(self._create_no_budget_alert(cat, spent))
                continue

            ratio = spent / budgeted

            if ratio > self.config["at_limit_threshold"]:
                # Overspent
                alerts.append(self._create_alert(
                    cat, spent, budgeted, ratio, AlertSeverity.CRITICAL, "overspent"
                ))
            elif ratio >= self.config["approaching_threshold"]:
                # Approaching limit
                alerts.append(self._create_alert(
                    cat, spent, budgeted, ratio, AlertSeverity.INFO, "approaching"
                ))

        return alerts

    def _create_alert(self, cat, spent: int, budgeted: int, ratio: float,
                      severity: AlertSeverity, status: str) -> Alert:
        """Create an alert for budget overspending."""
        spent_dollars = milliunits_to_dollars(spent)
        budget_dollars = milliunits_to_dollars(budgeted)
        overspent = spent - budgeted if spent > budgeted else 0
        overspent_dollars = milliunits_to_dollars(overspent)

        category_name = cat['name']
        group_name = cat['category_group_name'] or ""

        if status == "overspent":
            title = f"{category_name} is overspent"
            description = (
                f"Spent ${spent_dollars:,.2f} of ${budget_dollars:,.2f} budget "
                f"({ratio:.0%}). Over by ${overspent_dollars:,.2f}."
            )
        else:
            remaining = budgeted - spent
            remaining_dollars = milliunits_to_dollars(remaining)
            title = f"{category_name} approaching budget limit"
            description = (
                f"Spent ${spent_dollars:,.2f} of ${budget_dollars:,.2f} budget "
                f"({ratio:.0%}). ${remaining_dollars:,.2f} remaining."
            )

        return Alert(
            alert_type=AlertType.BUDGET_OVERSPENDING,
            severity=severity,
            title=title,
            description=description,
            related_entity_id=cat['id'],
            related_entity_type="category",
            metadata={
                "category_name": category_name,
                "category_group": group_name,
                "spent": spent,
                "budgeted": budgeted,
                "ratio": round(ratio, 3),
                "balance": cat['balance'] or 0,
                "status": status
            }
        )

    def _create_no_budget_alert(self, cat, spent: int) -> Alert:
        """Create alert for spending without budget."""
        spent_dollars = milliunits_to_dollars(spent)
        category_name = cat['name']
        group_name = cat['category_group_name'] or ""

        return Alert(
            alert_type=AlertType.BUDGET_OVERSPENDING,
            severity=AlertSeverity.WARNING,
            title=f"Spending without budget: {category_name}",
            description=f"Spent ${spent_dollars:,.2f} in category with no budget assigned.",
            related_entity_id=cat['id'],
            related_entity_type="category",
            metadata={
                "category_name": category_name,
                "category_group": group_name,
                "spent": spent,
                "budgeted": 0,
                "status": "no_budget"
            }
        )

    def get_config_schema(self) -> dict:
        """Return configuration schema for this detector."""
        return {
            "approaching_threshold": {
                "type": "float",
                "default": 0.90,
                "min": 0.5,
                "max": 0.99,
                "description": "Percentage of budget to trigger 'approaching' alert"
            },
            "at_limit_threshold": {
                "type": "float",
                "default": 1.00,
                "min": 0.9,
                "max": 1.5,
                "description": "Percentage of budget to trigger 'at limit' alert"
            },
            "ignore_zero_budget": {
                "type": "bool",
                "default": True,
                "description": "Skip categories with no budget assigned"
            },
            "alert_zero_budget_spending": {
                "type": "bool",
                "default": True,
                "description": "Alert when spending occurs in categories without budget"
            }
        }


# Register the detector
AlertRegistry.register(BudgetOverspendingDetector)
