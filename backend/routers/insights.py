"""Insights router — spending analytics aggregates for charts/dashboards.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. All monetary fields are milliunits (see backend.schemas).

These endpoints wrap the read-only analytics queries on
:class:`~src.cache.database.Database`:

* ``get_spending_by_category`` sums ``ABS(amount)`` of *outflows* (amount < 0)
  over the trailing ``months`` window, grouped by category. ``total_amount`` is
  therefore a positive milliunit total of money spent.
* ``get_monthly_spending_trend`` sums ``ABS(amount)`` of outflows per calendar
  month (``YYYY-MM``) over the trailing ``months`` window.

The aggregate shapes are not in ``backend.schemas`` (they're analytics-only), so
small response models are defined inline here. Rows are ``sqlite3.Row`` and are
mapped via ``Model.model_validate(dict(row))`` — the SELECT aliases match the
model fields one-to-one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional

from backend.deps import get_budget_id, get_db
from src.cache.database import Database

router = APIRouter(tags=["insights"])


class SpendingByCategory(BaseModel):
    """Total outflow spending for a single category over a window.

    ``total_amount`` is a positive milliunit sum of ``ABS(amount)`` for outflow
    transactions; ``category_id`` / ``category_name`` are null for uncategorized
    spending.
    """

    category_id: Optional[str] = Field(None, description="Category id, or null if uncategorized.")
    category_name: Optional[str] = Field(None, description="Category name, or null if uncategorized.")
    total_amount: int = Field(..., description="Positive milliunit sum of outflows.")
    transaction_count: int = Field(..., description="Number of outflow transactions.")


class MonthlyTrendPoint(BaseModel):
    """Total outflow spending for one calendar month."""

    month: str = Field(..., description="Calendar month as YYYY-MM.")
    total_amount: int = Field(..., description="Positive milliunit sum of outflows in the month.")


@router.get("/insights/spending-by-category", response_model=list[SpendingByCategory])
def spending_by_category(
    months: int = Query(1, ge=1, description="Trailing window size in months."),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[SpendingByCategory]:
    """Total outflow spending grouped by category over the trailing window."""
    rows = db.get_spending_by_category(budget_id, months=months)
    return [SpendingByCategory.model_validate(dict(row)) for row in rows]


@router.get("/insights/monthly-trend", response_model=list[MonthlyTrendPoint])
def monthly_trend(
    months: int = Query(12, ge=1, description="Trailing window size in months."),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[MonthlyTrendPoint]:
    """Monthly outflow spending totals over the trailing window (oldest first)."""
    rows = db.get_monthly_spending_trend(budget_id, months=months)
    return [MonthlyTrendPoint.model_validate(dict(row)) for row in rows]
