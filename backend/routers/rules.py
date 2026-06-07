"""Auto-categorization rules router — wraps the rule CRUD on
:class:`~src.cache.database.Database` plus an "apply-now" action.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it.

A rule matches a payee/memo ``pattern`` and assigns a category. Rows come back
from ``Database.get_rules`` already JOINed with their category, so each row
carries the ``category_name`` and ``group_name`` columns the ``Rule`` wire model
declares; ``schemas.Rule.model_validate(dict(row))`` maps them one-to-one (the
extra ``budget_id`` column is ignored by Pydantic).

There is no ``get_single_rule`` on Database, so to fetch one rule (after create,
or to check existence) we read ``get_rules`` and find the matching id.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend import schemas
from backend.deps import get_budget_id, get_db, get_import_service
from src.cache.database import Database
from src.imports.service import ImportService

router = APIRouter(tags=["rules"])


def _to_rule(row) -> schemas.Rule:
    """Map a joined ``sqlite3.Row`` from get_rules onto the wire model."""
    return schemas.Rule.model_validate(dict(row))


def _find_rule(db: Database, budget_id: str, rule_id: int) -> Optional[object]:
    """Return the joined rule row for ``rule_id`` or None (no single-rule query)."""
    for row in db.get_rules(budget_id):
        if row["id"] == rule_id:
            return row
    return None


def _get_rule_or_404(db: Database, budget_id: str, rule_id: int):
    """Fetch a rule row or raise 404 if it doesn't exist."""
    row = _find_rule(db, budget_id, rule_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found",
        )
    return row


@router.get("/rules", response_model=list[schemas.Rule])
def list_rules(
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.Rule]:
    """List auto-categorization rules for the local budget (priority order)."""
    return [_to_rule(row) for row in db.get_rules(budget_id)]


@router.post(
    "/rules",
    response_model=schemas.Rule,
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    req: schemas.RuleCreateRequest,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.Rule:
    """Create an auto-categorization rule.

    The target ``category_id`` must already exist (400 otherwise). After
    inserting, the new rule is re-fetched via ``get_rules`` so the response
    carries the joined ``category_name`` / ``group_name``.
    """
    if db.get_category(req.category_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category {req.category_id!r} not found",
        )
    rule_id = db.add_rule(
        budget_id,
        req.pattern,
        req.category_id,
        match_field=req.match_field,
        match_type=req.match_type,
        priority=req.priority,
    )
    return _to_rule(_get_rule_or_404(db, budget_id, rule_id))


@router.delete("/rules/{rule_id}", response_model=schemas.MessageResponse)
def delete_rule(
    rule_id: int,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Delete an auto-categorization rule (404 if it doesn't exist)."""
    _get_rule_or_404(db, budget_id, rule_id)
    db.delete_rule(rule_id)
    return schemas.MessageResponse(status="ok", message=f"Rule {rule_id} deleted")


@router.post("/rules/{rule_id}/apply", response_model=schemas.MessageResponse)
def apply_rule(
    rule_id: int,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
    service: ImportService = Depends(get_import_service),
) -> schemas.MessageResponse:
    """Apply an existing rule to already-imported, uncategorized transactions.

    Returns the number of transactions categorized in the message. 404 if the
    rule doesn't exist (so callers don't silently get a count of 0 for a typo'd
    id — ``apply_rule_to_existing`` itself returns 0 for an unknown rule).
    """
    _get_rule_or_404(db, budget_id, rule_id)
    count = service.apply_rule_to_existing(rule_id)
    return schemas.MessageResponse(
        status="ok", message=f"Applied rule to {count} transactions"
    )
