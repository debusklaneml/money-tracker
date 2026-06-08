"""Configuration management for BUD (local-first budgeting app)."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AlertThresholds:
    """Alert detection thresholds."""
    unusual_spending_warning: float = 2.5
    unusual_spending_critical: float = 3.5
    budget_approaching: float = 0.90
    recurring_days_warning: int = 3
    recurring_days_critical: int = 7
    recurring_amount_tolerance_percent: float = 5.0
    recurring_amount_tolerance_absolute: int = 100  # milliunits ($0.10)


def load_alert_thresholds() -> AlertThresholds:
    """Return default alert thresholds.

    Previously these were sourced from Streamlit secrets; with the Streamlit UI
    removed, defaults are used. Configurable thresholds can be reintroduced via
    the FastAPI backend if needed.
    """
    return AlertThresholds()


def get_db_path() -> Path:
    """Location of the local SQLite database."""
    return Path.home() / ".bud" / "cache.db"
