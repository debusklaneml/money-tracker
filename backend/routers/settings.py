"""Settings router — dashboard summary counts and destructive data reset.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. All monetary fields are milliunits (see backend.schemas).

Endpoints:

* ``GET /settings/summary`` returns a small roll-up for a settings/dashboard
  page: counts of accounts, categories, transactions, rules and active alerts,
  plus the current budget month and ready-to-assign from
  :meth:`BudgetEngine.get_state`, and the on-disk DB path.
* ``POST /settings/clear-data`` is DESTRUCTIVE — see its docstring.

The summary shape is settings-only and not part of ``backend.schemas``, so it is
defined inline. ``transaction_count`` is the length of a large
``get_transactions`` page (limit ``_TXN_COUNT_LIMIT``); this is a simple,
correct count for current data sizes — replace with a SQL COUNT if datasets grow
past that ceiling.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend import schemas
from backend.deps import get_budget_id, get_db, get_engine
from src.budget.engine import BudgetEngine
from src.cache.database import Database

router = APIRouter(tags=["settings"])

# Upper bound for the in-memory transaction count (see module docstring).
_TXN_COUNT_LIMIT = 1_000_000


class SettingsSummary(BaseModel):
    """Roll-up counts and state for the settings/dashboard page."""

    account_count: int = Field(..., description="Number of accounts.")
    category_count: int = Field(..., description="Number of visible categories.")
    transaction_count: int = Field(..., description="Number of non-deleted transactions.")
    uncategorized_count: int = Field(..., description="Number of uncategorized transactions.")
    rule_count: int = Field(..., description="Number of auto-categorization rules.")
    active_alert_count: int = Field(..., description="Number of non-dismissed alerts.")
    current_month: str = Field(..., description="Current budget month as YYYY-MM-01.")
    ready_to_assign: int = Field(
        ..., description="Milliunits available to assign (cumulative income - assigned)."
    )
    db_path: str = Field(..., description="Filesystem path to the SQLite database.")


@router.get("/settings/summary", response_model=SettingsSummary)
def settings_summary(
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
    engine: BudgetEngine = Depends(get_engine),
) -> SettingsSummary:
    """Return roll-up counts and current budget state for the settings page."""
    state = engine.get_state()
    return SettingsSummary(
        account_count=len(db.get_accounts(budget_id)),
        category_count=len(db.get_categories(budget_id)),
        transaction_count=len(db.get_transactions(budget_id, limit=_TXN_COUNT_LIMIT)),
        uncategorized_count=db.count_uncategorized(budget_id),
        rule_count=len(db.get_rules(budget_id)),
        active_alert_count=len(db.get_alerts(budget_id)),
        current_month=state.month,
        ready_to_assign=state.ready_to_assign,
        db_path=str(db.db_path),
    )


@router.post("/settings/clear-data", response_model=schemas.MessageResponse)
def clear_data(
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """DESTRUCTIVE: delete imported transactions, accounts, import history and
    alerts for the local budget.

    Categories, auto-categorization rules and monthly assignments are KEPT, so
    the budget structure survives — only the imported data is wiped. This cannot
    be undone.
    """
    db.clear_imported_data(budget_id)
    return schemas.MessageResponse(
        status="ok",
        message="Cleared imported transactions, accounts, import history and alerts.",
    )
