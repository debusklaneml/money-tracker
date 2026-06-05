"""Configuration management for BUD (local-first budgeting app)."""

from dataclasses import dataclass
from pathlib import Path

import streamlit as st


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
    """Load alert thresholds from Streamlit secrets, falling back to defaults."""
    try:
        section = st.secrets.get("alert_thresholds", {})
    except Exception:
        section = {}
    return AlertThresholds(
        unusual_spending_warning=float(section.get("unusual_spending_warning", 2.5)),
        unusual_spending_critical=float(section.get("unusual_spending_critical", 3.5)),
        budget_approaching=float(section.get("budget_approaching", 0.90)),
        recurring_days_warning=int(section.get("recurring_days_warning", 3)),
        recurring_days_critical=int(section.get("recurring_days_critical", 7)),
    )


def get_db_path() -> Path:
    """Location of the local SQLite database."""
    return Path.home() / ".bud" / "cache.db"
