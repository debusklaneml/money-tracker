"""Pydantic models for YNAB data."""

from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


def milliunits_to_decimal(milliunits: int) -> Decimal:
    """Convert YNAB milliunits to decimal currency."""
    return Decimal(milliunits) / 1000


def decimal_to_milliunits(amount: Decimal) -> int:
    """Convert decimal currency to YNAB milliunits."""
    return int(amount * 1000)


class Budget(BaseModel):
    """YNAB Budget model."""
    id: str
    name: str
    last_modified_on: Optional[str] = None
    first_month: Optional[str] = None
    last_month: Optional[str] = None
    currency_format: Optional[str] = None


class Account(BaseModel):
    """YNAB Account model."""
    id: str
    budget_id: str
    name: str
    type: str
    on_budget: bool
    closed: bool
    balance: int  # milliunits
    cleared_balance: int
    uncleared_balance: int

    @property
    def balance_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.balance)


class Category(BaseModel):
    """YNAB Category model."""
    id: str
    budget_id: str
    category_group_id: Optional[str] = None
    category_group_name: Optional[str] = None
    name: str
    hidden: bool = False
    budgeted: int = 0  # milliunits
    activity: int = 0
    balance: int = 0
    goal_type: Optional[str] = None
    goal_target: Optional[int] = None
    goal_target_month: Optional[str] = None

    @property
    def budgeted_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.budgeted)

    @property
    def activity_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.activity)

    @property
    def balance_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.balance)


class Transaction(BaseModel):
    """YNAB Transaction model."""
    id: str
    budget_id: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    date: date
    amount: int  # milliunits
    memo: Optional[str] = None
    cleared: str = "uncleared"
    approved: bool = False
    flag_color: Optional[str] = None
    payee_id: Optional[str] = None
    payee_name: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    transfer_account_id: Optional[str] = None
    transfer_transaction_id: Optional[str] = None
    import_id: Optional[str] = None
    deleted: bool = False

    @property
    def amount_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.amount)

    @property
    def is_outflow(self) -> bool:
        return self.amount < 0

    @property
    def is_inflow(self) -> bool:
        return self.amount > 0


class ScheduledTransaction(BaseModel):
    """YNAB Scheduled Transaction model."""
    id: str
    budget_id: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    date_first: date
    date_next: date
    frequency: str
    amount: int  # milliunits
    memo: Optional[str] = None
    payee_id: Optional[str] = None
    payee_name: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    deleted: bool = False

    @property
    def amount_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.amount)


class MonthBudget(BaseModel):
    """Monthly budget category entry."""
    budget_id: str
    month: str
    category_id: str
    budgeted: int = 0
    activity: int = 0
    balance: int = 0

    @property
    def budgeted_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.budgeted)

    @property
    def activity_decimal(self) -> Decimal:
        return milliunits_to_decimal(self.activity)


class Alert(BaseModel):
    """Alert model."""
    id: Optional[int] = None
    budget_id: str
    alert_type: str
    severity: str
    title: str
    description: str
    related_entity_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    dismissed: bool = False
