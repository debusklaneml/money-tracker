"""Configuration management for BUD app."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
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


@dataclass
class SyncConfig:
    """Sync configuration."""
    auto_sync_interval_minutes: int = 30


@dataclass
class AppConfig:
    """Application configuration."""
    ynab_token: str
    db_path: Path
    alerts: AlertThresholds = field(default_factory=AlertThresholds)
    sync: SyncConfig = field(default_factory=SyncConfig)


def load_config() -> AppConfig:
    """Load configuration from Streamlit secrets."""
    # Required: YNAB token
    token = st.secrets.get("YNAB_ACCESS_TOKEN")
    if not token:
        raise ValueError("YNAB_ACCESS_TOKEN not found in secrets")

    # Alert thresholds
    alert_section = st.secrets.get("alert_thresholds", {})
    alerts = AlertThresholds(
        unusual_spending_warning=float(alert_section.get("unusual_spending_warning", 2.5)),
        unusual_spending_critical=float(alert_section.get("unusual_spending_critical", 3.5)),
        budget_approaching=float(alert_section.get("budget_approaching", 0.90)),
        recurring_days_warning=int(alert_section.get("recurring_days_warning", 3)),
        recurring_days_critical=int(alert_section.get("recurring_days_critical", 7)),
    )

    # Sync config
    sync_section = st.secrets.get("sync", {})
    sync = SyncConfig(
        auto_sync_interval_minutes=int(sync_section.get("auto_sync_interval_minutes", 30))
    )

    # Database path
    db_path = Path.home() / ".bud" / "cache.db"

    return AppConfig(
        ynab_token=token,
        alerts=alerts,
        sync=sync,
        db_path=db_path
    )


def get_token_from_secrets() -> Optional[str]:
    """Get YNAB token from secrets, returns None if not found."""
    try:
        return st.secrets.get("YNAB_ACCESS_TOKEN")
    except Exception:
        return None


def validate_token(token: str) -> bool:
    """Validate that a token string looks valid."""
    if not token:
        return False
    # YNAB tokens are typically long strings
    if len(token) < 20:
        return False
    # Basic format check
    if " " in token or "\n" in token:
        return False
    return True
