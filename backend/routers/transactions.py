"""Transactions router — list/filter transactions and (bulk) categorize them.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. All monetary fields are milliunits (see backend.schemas).

Database rows are ``sqlite3.Row`` and are mapped onto the ``Transaction`` wire
model with ``schemas.Transaction.model_validate(dict(row))``. The row's column
names match the schema fields one-to-one; ``approved`` and ``deleted`` are stored
as ints (0/1) and Pydantic v2 coerces them to ``bool``. The extra ``budget_id``
column is ignored by Pydantic.

Filtering note
--------------
:class:`~src.cache.database.Database` has no single query covering all the
filters this router exposes, so filtering by ``category_id`` / ``account_id`` /
``search`` is done **in memory** within the router: a generous page is fetched
via ``get_transactions`` (honouring ``limit``/``offset``) and then narrowed in
Python. ``search`` is a case-insensitive substring match over ``payee_name``,
``memo`` and ``category_name``. The ``uncategorized`` flag short-circuits to
``get_uncategorized_transactions`` (account_id/search filters are still applied
on top of that result). This is intentionally simple and correct for the current
data sizes; push the filters down into SQL later if it becomes a bottleneck.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend import schemas
from backend.deps import get_budget_id, get_db
from src.cache.database import Database

router = APIRouter(tags=["transactions"])


class BulkCategorizeRequest(BaseModel):
    """Assign (or clear) the category of many transactions at once."""

    transaction_ids: list[str] = Field(
        ..., description="Ids of the transactions to (re)categorize."
    )
    category_id: Optional[str] = Field(
        None, description="Category id to assign to all; null clears the category."
    )
    category_name: Optional[str] = Field(
        None, description="Category name to store; resolved from the id if omitted."
    )


def _to_transaction(row) -> schemas.Transaction:
    """Map a ``sqlite3.Row`` from the transactions table onto the wire model."""
    return schemas.Transaction.model_validate(dict(row))


def _matches(row, account_id: Optional[str], search: Optional[str]) -> bool:
    """Apply the in-memory account_id / search filters to a single row."""
    if account_id is not None and row["account_id"] != account_id:
        return False
    if search:
        needle = search.lower()
        haystack = " ".join(
            str(row[field] or "")
            for field in ("payee_name", "memo", "category_name")
        ).lower()
        if needle not in haystack:
            return False
    return True


def _resolve_category_name(
    db: Database, category_id: Optional[str], category_name: Optional[str]
) -> Optional[str]:
    """Keep the denormalized category name correct.

    If a ``category_id`` is supplied without a name, look the name up so the
    stored ``category_name`` matches the id. When the id is null (clearing the
    category) the name is forced to null too.
    """
    if category_id is None:
        return None
    if category_name is not None:
        return category_name
    row = db.get_category(category_id)
    return row["name"] if row is not None else None


@router.get("/transactions", response_model=list[schemas.Transaction])
def list_transactions(
    category_id: Optional[str] = Query(
        None, description="Only transactions in this category (in-memory filter)."
    ),
    account_id: Optional[str] = Query(
        None, description="Only transactions in this account (in-memory filter)."
    ),
    search: Optional[str] = Query(
        None,
        description=(
            "Case-insensitive substring over payee_name, memo and category_name "
            "(in-memory filter)."
        ),
    ),
    uncategorized: bool = Query(
        False,
        description=(
            "Return only uncategorized transactions. account_id/search still "
            "apply; category_id is ignored in this mode."
        ),
    ),
    limit: int = Query(100, ge=1, description="Max rows to fetch from the DB page."),
    offset: int = Query(0, ge=0, description="Row offset into the DB page."),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.Transaction]:
    """List transactions for the local budget with optional filters.

    Filtering by ``category_id`` / ``account_id`` / ``search`` is performed in
    memory (see the module docstring). When ``uncategorized`` is true the
    uncategorized set is used as the source and ``category_id`` is ignored.
    """
    if uncategorized:
        rows = db.get_uncategorized_transactions(budget_id, limit=limit)
    else:
        rows = db.get_transactions(budget_id, limit=limit, offset=offset)
        if category_id is not None:
            rows = [r for r in rows if r["category_id"] == category_id]

    rows = [r for r in rows if _matches(r, account_id, search)]
    return [_to_transaction(r) for r in rows]


@router.get("/transactions/uncategorized", response_model=list[schemas.Transaction])
def list_uncategorized(
    limit: int = Query(500, ge=1, description="Max uncategorized rows to return."),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.Transaction]:
    """List uncategorized transactions (those with no category assigned)."""
    rows = db.get_uncategorized_transactions(budget_id, limit=limit)
    return [_to_transaction(r) for r in rows]


@router.get("/transactions/uncategorized/count", response_model=int)
def count_uncategorized(
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> int:
    """Count uncategorized transactions for the local budget."""
    return db.count_uncategorized(budget_id)


@router.patch("/transactions/{txn_id}", response_model=schemas.MessageResponse)
def categorize_transaction(
    txn_id: str,
    body: schemas.TransactionCategorizeRequest,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Assign (or clear) the category of a single transaction.

    If ``category_id`` is provided without a ``category_name``, the name is
    looked up from the category so the denormalized name stays correct.
    """
    category_name = _resolve_category_name(db, body.category_id, body.category_name)
    db.set_transaction_category(txn_id, body.category_id, category_name)
    return schemas.MessageResponse(
        status="ok", message=f"Transaction {txn_id} categorized."
    )


@router.post("/transactions/bulk-categorize", response_model=schemas.MessageResponse)
def bulk_categorize_transactions(
    body: BulkCategorizeRequest,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Categorize many transactions in one call.

    The ``category_name`` is resolved from the id once (if not supplied) and the
    same id/name pair is applied to every transaction in ``transaction_ids``.
    """
    category_name = _resolve_category_name(db, body.category_id, body.category_name)
    for txn_id in body.transaction_ids:
        db.set_transaction_category(txn_id, body.category_id, category_name)
    updated = len(body.transaction_ids)
    return schemas.MessageResponse(
        status="ok", message=f"Categorized {updated} transaction(s)."
    )
