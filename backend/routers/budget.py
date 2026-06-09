"""Budget router — wraps :class:`~src.budget.engine.BudgetEngine`.

Exposes the read-side budget state plus the two core writes (assign and move).
``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. All monetary amounts are milliunits (see backend.schemas).

The engine's ``BudgetState`` / ``CategoryState`` dataclasses share field names
with the matching Pydantic models, so responses are built with
``schemas.BudgetState.model_validate(state, from_attributes=True)``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend import schemas
from backend.deps import get_engine
from src.budget.engine import BudgetEngine, RTAExceededError, current_month

router = APIRouter(tags=["budget"])


def _state(engine: BudgetEngine, month: Optional[str]) -> schemas.BudgetState:
    """Compute the budget state and validate it onto the wire model."""
    state = engine.get_state(month)
    return schemas.BudgetState.model_validate(state, from_attributes=True)


@router.get("/budget", response_model=schemas.BudgetState)
def get_budget(
    month: Optional[str] = Query(
        None, description="Budget month as YYYY-MM-01; defaults to the current month."
    ),
    engine: BudgetEngine = Depends(get_engine),
) -> schemas.BudgetState:
    """Return the full budget state for ``month`` (default: current month)."""
    return _state(engine, month)


@router.post("/budget/assign", response_model=schemas.BudgetState)
def assign(
    req: schemas.AssignRequest,
    engine: BudgetEngine = Depends(get_engine),
) -> schemas.BudgetState:
    """Set a category's assigned amount for a month, returning fresh state.

    Rejects assignments that would push Ready to Assign below zero with a 400 —
    you cannot assign money that does not exist yet. The error detail reports
    how much is actually assignable to the category.
    """
    month = req.month or current_month()
    try:
        engine.assign(req.category_id, req.amount, month)
    except RTAExceededError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot assign {exc.requested}: only {exc.available} is "
                "available to assign for this month."
            ),
        ) from exc
    return _state(engine, month)


@router.post("/budget/move", response_model=schemas.BudgetState)
def move(
    req: schemas.MoveRequest,
    engine: BudgetEngine = Depends(get_engine),
) -> schemas.BudgetState:
    """Move money between two categories for a month, returning fresh state."""
    month = req.month or current_month()
    engine.move(req.from_id, req.to_id, req.amount, month)
    return _state(engine, month)
