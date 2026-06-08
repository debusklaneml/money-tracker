"""Pydantic v2 request/response models for the bud API.

These are the wire/serialization layer between the FastAPI routers and the
core domain logic in ``src/`` (Database, BudgetEngine, ImportService). They
mirror the dataclasses and SQLite row shapes defined there, but they are pure
data models: this module imports nothing from ``src/`` and has no side effects
on import.

Money convention
----------------
ALL monetary amounts are integers in **milliunits** (1/1000 of a currency
unit, so $1.00 == 1000). Inflows are positive, outflows negative — the same
convention the engine and database use. Money fields are therefore always
``int``, never ``float``, to avoid rounding error.

Months are represented as ``YYYY-MM-01`` strings (the engine's
``current_month()`` format). Dates on transactions are ISO ``YYYY-MM-DD``
strings as stored in SQLite.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Categories & budget state (mirror BudgetEngine's CategoryState / BudgetState)
# ---------------------------------------------------------------------------
class CategoryState(BaseModel):
    """A single category's state for a given month.

    Mirrors ``src.budget.engine.CategoryState``. ``assigned`` and ``activity``
    are scoped to the requested month; ``available`` is the rolling balance
    through that month (so unspent money carries forward).
    """

    id: str = Field(..., description="Category id (uuid hex).")
    group: str = Field(..., description="Category group name, e.g. 'Bills'.")
    name: str = Field(..., description="Category name, e.g. 'Groceries'.")
    assigned: int = Field(..., description="Milliunits assigned this month.")
    activity: int = Field(
        ..., description="Milliunits of activity this month (negative = spending)."
    )
    available: int = Field(
        ..., description="Milliunits available (rolling balance through this month)."
    )


class BudgetState(BaseModel):
    """The full budget state for a month, including Ready-to-Assign.

    Mirrors ``src.budget.engine.BudgetState``. ``ready_to_assign`` is
    cumulative income minus cumulative assigned through ``month``; spending
    does not reduce it (it reduces a category's ``available``).
    """

    month: str = Field(..., description="Budget month as YYYY-MM-01.")
    ready_to_assign: int = Field(
        ..., description="Milliunits available to assign (cumulative income - assigned)."
    )
    income_month: int = Field(..., description="Milliunits of income in this month.")
    income_total: int = Field(
        ..., description="Cumulative milliunits of income through this month."
    )
    assigned_total: int = Field(
        ..., description="Cumulative milliunits assigned through this month."
    )
    categories: list[CategoryState] = Field(
        default_factory=list, description="Per-category state for this month."
    )


class CategoryGroup(BaseModel):
    """A category group with its member categories, for grouped display."""

    name: str = Field(..., description="Group name, e.g. 'Bills'.")
    categories: list[CategoryState] = Field(
        default_factory=list, description="Categories belonging to this group."
    )


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------
class Category(BaseModel):
    """A category as stored (the ``categories`` table row).

    Money fields (``budgeted``, ``activity``, ``balance``, ``goal_target``) are
    milliunits.
    """

    id: str = Field(..., description="Category id (uuid hex).")
    category_group_id: Optional[str] = Field(
        None, description="Group id (lowercased group name)."
    )
    category_group_name: Optional[str] = Field(None, description="Group display name.")
    name: str = Field(..., description="Category name.")
    hidden: bool = Field(False, description="Whether the category is hidden/archived.")
    budgeted: int = Field(0, description="Milliunits budgeted (denormalized current).")
    activity: int = Field(0, description="Milliunits of activity (denormalized current).")
    balance: int = Field(0, description="Milliunits available (denormalized current).")
    goal_type: Optional[str] = Field(None, description="Goal type, if any.")
    goal_target: Optional[int] = Field(None, description="Goal target in milliunits.")
    goal_target_month: Optional[str] = Field(
        None, description="Goal target month as YYYY-MM-01."
    )
    sort_order: int = Field(0, description="Display sort order within the budget.")


class CategoryCreateRequest(BaseModel):
    """Create a new category in a group."""

    group: str = Field(..., description="Group name; created if it doesn't exist.")
    name: str = Field(..., description="New category name.")


class CategoryUpdateRequest(BaseModel):
    """Rename a category and/or move it to another group."""

    name: str = Field(..., description="New category name.")
    group: str = Field(..., description="Target group name.")


# ---------------------------------------------------------------------------
# Assign / move requests (BudgetEngine writes)
# ---------------------------------------------------------------------------
class AssignRequest(BaseModel):
    """Set a category's assigned amount for a month (BudgetEngine.assign)."""

    category_id: str = Field(..., description="Category to assign to.")
    amount: int = Field(..., description="Milliunits to set as the month's assignment.")
    month: Optional[str] = Field(
        None, description="Budget month YYYY-MM-01; defaults to the current month."
    )


class MoveRequest(BaseModel):
    """Move money between two categories for a month (BudgetEngine.move)."""

    from_id: str = Field(..., description="Source category id.")
    to_id: str = Field(..., description="Destination category id.")
    amount: int = Field(..., description="Milliunits to move from source to destination.")
    month: Optional[str] = Field(
        None, description="Budget month YYYY-MM-01; defaults to the current month."
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
class Account(BaseModel):
    """A bank/credit account (the ``accounts`` table row). Balances are milliunits."""

    id: str = Field(..., description="Account id.")
    name: str = Field(..., description="Account display name.")
    type: Optional[str] = Field(None, description="Account type, e.g. 'checking'.")
    on_budget: bool = Field(True, description="Whether the account is on-budget.")
    closed: bool = Field(False, description="Whether the account is closed.")
    balance: int = Field(0, description="Current balance in milliunits.")
    cleared_balance: int = Field(0, description="Cleared balance in milliunits.")
    uncleared_balance: int = Field(0, description="Uncleared balance in milliunits.")
    account_number: Optional[str] = Field(
        None, description="Bank account number (import key)."
    )


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------
class Transaction(BaseModel):
    """A transaction (the ``transactions`` table row).

    ``amount`` is in milliunits, signed (negative = outflow). ``import_id``
    holds the bank FITID used for dedupe.
    """

    id: str = Field(..., description="Transaction id (uuid hex).")
    account_id: Optional[str] = Field(None, description="Owning account id.")
    account_name: Optional[str] = Field(None, description="Owning account name.")
    date: str = Field(..., description="Transaction date as ISO YYYY-MM-DD.")
    amount: int = Field(..., description="Signed milliunits (negative = outflow).")
    memo: Optional[str] = Field(None, description="Free-text memo.")
    cleared: Optional[str] = Field(
        None, description="Cleared status, e.g. 'cleared' / 'uncleared'."
    )
    approved: bool = Field(True, description="Whether the transaction is approved.")
    flag_color: Optional[str] = Field(None, description="Optional flag color.")
    payee_id: Optional[str] = Field(None, description="Payee id, if known.")
    payee_name: Optional[str] = Field(None, description="Payee name.")
    category_id: Optional[str] = Field(None, description="Assigned category id, if any.")
    category_name: Optional[str] = Field(None, description="Assigned category name, if any.")
    transfer_account_id: Optional[str] = Field(
        None, description="Other account id for transfers."
    )
    transfer_transaction_id: Optional[str] = Field(
        None, description="Paired transaction id for transfers."
    )
    import_id: Optional[str] = Field(None, description="Bank FITID used for dedupe.")
    deleted: bool = Field(False, description="Soft-delete flag.")


class TransactionCategorizeRequest(BaseModel):
    """Assign (or clear) the category of a single transaction."""

    category_id: Optional[str] = Field(
        None, description="Category id to assign; null clears the category."
    )
    category_name: Optional[str] = Field(
        None, description="Category name to store alongside the id."
    )


# ---------------------------------------------------------------------------
# Auto-categorization rules (the ``category_rules`` table)
# ---------------------------------------------------------------------------
class Rule(BaseModel):
    """An auto-categorization rule: match a payee/memo pattern to a category.

    Mirrors a ``category_rules`` row joined with its category. ``match_field``
    is 'payee' | 'memo'; ``match_type`` is 'contains' | 'equals' | 'regex'.
    Lower ``priority`` numbers are applied first.
    """

    id: int = Field(..., description="Rule id (autoincrement).")
    match_field: str = Field(
        "payee", description="Field to match against: 'payee' or 'memo'."
    )
    match_type: str = Field(
        "contains", description="Match type: 'contains', 'equals', or 'regex'."
    )
    pattern: str = Field(..., description="Pattern to match.")
    category_id: str = Field(..., description="Category to apply on match.")
    category_name: Optional[str] = Field(None, description="Category name (joined).")
    group_name: Optional[str] = Field(None, description="Category group name (joined).")
    priority: int = Field(100, description="Lower runs first.")


class RuleCreateRequest(BaseModel):
    """Create an auto-categorization rule."""

    pattern: str = Field(..., description="Pattern to match.")
    category_id: str = Field(..., description="Category to apply on match.")
    match_field: str = Field("payee", description="'payee' or 'memo'.")
    match_type: str = Field(
        "contains", description="'contains', 'equals', or 'regex'."
    )
    priority: int = Field(100, description="Lower runs first.")


# ---------------------------------------------------------------------------
# Imports (mirror ImportService.ImportResult / import batches)
# ---------------------------------------------------------------------------
class ImportResult(BaseModel):
    """Result of importing an OFX/QFX file.

    Mirrors ``src.imports.service.ImportResult``. Dedupe is by bank FITID
    (per account) and by file hash: ``duplicates`` counts transactions skipped
    because their FITID was already imported, while ``already_imported_file``
    flags that this exact file content was seen before.
    """

    filename: str = Field(..., description="Uploaded file name.")
    accounts: list[str] = Field(
        default_factory=list, description="Account labels touched by this import."
    )
    imported: int = Field(0, description="Count of newly inserted transactions.")
    duplicates: int = Field(
        0, description="Count of transactions skipped as FITID duplicates."
    )
    auto_categorized: int = Field(
        0, description="Count of imported transactions auto-categorized by rules."
    )
    already_imported_file: bool = Field(
        False, description="True if this file's content hash was imported before."
    )
    date_min: Optional[str] = Field(
        None, description="Earliest imported transaction date (ISO)."
    )
    date_max: Optional[str] = Field(
        None, description="Latest imported transaction date (ISO)."
    )


class ImportPreview(BaseModel):
    """A non-committing preview of what an import would do.

    Lets the UI show parsed accounts and the transactions that would be added
    vs. skipped as duplicates before the user commits the import. Money is in
    milliunits.
    """

    filename: str = Field(..., description="Uploaded file name.")
    accounts: list[str] = Field(
        default_factory=list, description="Account labels found in the file."
    )
    new_transactions: list[Transaction] = Field(
        default_factory=list, description="Transactions that would be inserted."
    )
    duplicate_count: int = Field(
        0, description="Count of transactions that would be skipped (FITID dupes)."
    )
    already_imported_file: bool = Field(
        False, description="True if this file's content hash was imported before."
    )
    date_min: Optional[str] = Field(None, description="Earliest parsed date (ISO).")
    date_max: Optional[str] = Field(None, description="Latest parsed date (ISO).")


class ImportBatch(BaseModel):
    """A recorded import batch (the ``import_batches`` table row), for history."""

    id: int = Field(..., description="Batch id (autoincrement).")
    account_id: Optional[str] = Field(None, description="Account this batch targeted.")
    filename: Optional[str] = Field(None, description="Imported file name.")
    file_hash: Optional[str] = Field(None, description="SHA-256 of the file content.")
    imported_at: Optional[str] = Field(None, description="Import timestamp (ISO).")
    txn_count: int = Field(0, description="Transactions inserted in this batch.")
    duplicate_count: int = Field(0, description="Transactions skipped as duplicates.")
    date_min: Optional[str] = Field(None, description="Earliest transaction date (ISO).")
    date_max: Optional[str] = Field(None, description="Latest transaction date (ISO).")


class ImportDeleteResult(BaseModel):
    """Result of deleting an import batch and its cascade-deleted transactions."""

    id: int = Field(..., description="Deleted batch id.")
    deleted_transactions: int = Field(
        0, description="Count of transactions removed along with the batch."
    )


# ---------------------------------------------------------------------------
# Alerts (mirror src.alerts)
# ---------------------------------------------------------------------------
class Alert(BaseModel):
    """A detected alert (the ``alerts`` table row / ``src.alerts.base.Alert``).

    ``alert_type`` is one of unusual_spending | budget_overspending |
    recurring_change | recurring_missing; ``severity`` is info | warning |
    critical. Any monetary values inside ``metadata`` are milliunits.
    """

    id: Optional[int] = Field(None, description="Alert id (autoincrement), if persisted.")
    alert_type: str = Field(..., description="Alert type identifier.")
    severity: str = Field(..., description="Severity: info | warning | critical.")
    title: str = Field(..., description="Short headline.")
    description: Optional[str] = Field(None, description="Human-readable detail.")
    related_entity_id: Optional[str] = Field(
        None, description="Id of the related entity (category/transaction/...)."
    )
    related_entity_type: Optional[str] = Field(
        None, description="Type of the related entity."
    )
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Structured extra data; monetary values are milliunits."
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO).")
    acknowledged_at: Optional[str] = Field(
        None, description="Acknowledgement timestamp (ISO), if any."
    )
    dismissed: bool = Field(False, description="Whether the alert is dismissed.")


# ---------------------------------------------------------------------------
# Generic responses
# ---------------------------------------------------------------------------
class MessageResponse(BaseModel):
    """A simple message/status envelope for endpoints with no richer payload."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field("ok", description="Status string, e.g. 'ok'.")
    message: Optional[str] = Field(None, description="Optional human-readable detail.")
