"""Accounts router — read-only listing of bank/credit accounts.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. All monetary fields are milliunits (see backend.schemas).

Database rows are ``sqlite3.Row`` and are mapped onto the ``Account`` wire model
with ``schemas.Account.model_validate(dict(row))``. The row carries an extra
``budget_id`` column the model doesn't declare — Pydantic ignores unknown keys.
``on_budget`` and ``closed`` are stored as ints (0/1) and Pydantic v2 coerces
them to ``bool``; ``account_number`` maps straight through.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend import schemas
from backend.deps import get_budget_id, get_db
from src.cache.database import Database

router = APIRouter(tags=["accounts"])


def _to_account(row) -> schemas.Account:
    """Map a ``sqlite3.Row`` from the accounts table onto the wire model."""
    return schemas.Account.model_validate(dict(row))


@router.get("/accounts", response_model=list[schemas.Account])
def list_accounts(
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.Account]:
    """List all accounts for the local budget."""
    rows = db.get_accounts(budget_id)
    return [_to_account(row) for row in rows]
