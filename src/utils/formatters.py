"""Formatting utilities for currency and dates."""

from decimal import Decimal
from datetime import date, datetime
from typing import Union


def milliunits_to_dollars(milliunits: int) -> Decimal:
    """Convert YNAB milliunits to dollars."""
    return Decimal(milliunits) / 1000


def dollars_to_milliunits(dollars: Union[Decimal, float]) -> int:
    """Convert dollars to YNAB milliunits."""
    return int(Decimal(str(dollars)) * 1000)


def format_currency(milliunits: int, show_sign: bool = False) -> str:
    """Format milliunits as a currency string."""
    dollars = milliunits_to_dollars(milliunits)
    if show_sign and dollars >= 0:
        return f"+${dollars:,.2f}"
    elif dollars < 0:
        return f"-${abs(dollars):,.2f}"
    return f"${dollars:,.2f}"


def format_currency_decimal(dollars: Decimal, show_sign: bool = False) -> str:
    """Format decimal dollars as a currency string."""
    if show_sign and dollars >= 0:
        return f"+${dollars:,.2f}"
    elif dollars < 0:
        return f"-${abs(dollars):,.2f}"
    return f"${dollars:,.2f}"


def format_date(d: Union[date, datetime, str]) -> str:
    """Format a date for display."""
    if isinstance(d, str):
        d = datetime.fromisoformat(d).date()
    elif isinstance(d, datetime):
        d = d.date()
    return d.strftime("%b %d, %Y")


def format_date_short(d: Union[date, datetime, str]) -> str:
    """Format a date in short form."""
    if isinstance(d, str):
        d = datetime.fromisoformat(d).date()
    elif isinstance(d, datetime):
        d = d.date()
    return d.strftime("%m/%d")


def format_month(month_str: str) -> str:
    """Format a YYYY-MM-DD month string for display."""
    try:
        d = datetime.strptime(month_str, "%Y-%m-%d")
        return d.strftime("%B %Y")
    except ValueError:
        return month_str


def parse_month(month_str: str) -> date:
    """Parse a month string to date object."""
    if len(month_str) == 7:  # YYYY-MM
        month_str = f"{month_str}-01"
    return datetime.strptime(month_str, "%Y-%m-%d").date()


def get_current_month() -> str:
    """Get current month in YNAB format (YYYY-MM-01)."""
    return datetime.now().strftime("%Y-%m-01")


def get_previous_months(count: int) -> list[str]:
    """Get list of previous month strings in YNAB format."""
    from dateutil.relativedelta import relativedelta

    current = datetime.now().replace(day=1)
    months = []
    for i in range(count):
        m = current - relativedelta(months=i)
        months.append(m.strftime("%Y-%m-01"))
    return months


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a decimal as a percentage."""
    return f"{value * 100:.{decimals}f}%"


def format_change(current: int, previous: int) -> str:
    """Format the change between two values as a percentage."""
    if previous == 0:
        if current == 0:
            return "0%"
        return "+100%" if current > 0 else "-100%"

    change = (current - previous) / abs(previous)
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1%}"
