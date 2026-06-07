"""Categories router — wraps the category CRUD on
:class:`~src.cache.database.Database`.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. All monetary fields are milliunits (see backend.schemas).

Database rows are ``sqlite3.Row``; they are turned into the ``Category`` wire
model with ``schemas.Category.model_validate(dict(row))``. The row carries an
extra ``budget_id`` column that the model doesn't declare — Pydantic ignores
unknown keys by default, so no explicit mapping is needed. ``hidden`` is stored
as an int (0/1) and Pydantic v2 coerces it to ``bool``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend import schemas
from backend.deps import get_budget_id, get_db
from src.cache.database import Database

router = APIRouter(tags=["categories"])


class CategoryHiddenRequest(BaseModel):
    """Hide or unhide a category."""

    hidden: bool = Field(..., description="True to hide/archive, False to unhide.")


def _to_category(row) -> schemas.Category:
    """Map a ``sqlite3.Row`` from the categories table onto the wire model."""
    return schemas.Category.model_validate(dict(row))


def _get_or_404(db: Database, category_id: str):
    """Fetch a category row or raise 404 if it doesn't exist."""
    row = db.get_category(category_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category {category_id!r} not found",
        )
    return row


@router.get("/categories", response_model=list[schemas.Category])
def list_categories(
    include_hidden: bool = Query(
        False, description="Include hidden/archived categories."
    ),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.Category]:
    """List categories for the local budget."""
    rows = db.get_categories(budget_id, include_hidden=include_hidden)
    return [_to_category(row) for row in rows]


@router.post(
    "/categories",
    response_model=schemas.Category,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    req: schemas.CategoryCreateRequest,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.Category:
    """Create a category in a group (the group is created if it doesn't exist)."""
    cat_id = db.create_category(budget_id, req.group, req.name)
    return _to_category(_get_or_404(db, cat_id))


@router.patch("/categories/{category_id}", response_model=schemas.Category)
def update_category(
    category_id: str,
    req: schemas.CategoryUpdateRequest,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.Category:
    """Rename a category and/or move it to another group."""
    _get_or_404(db, category_id)
    db.update_category(category_id, req.name, req.group)
    return _to_category(_get_or_404(db, category_id))


@router.patch("/categories/{category_id}/hidden", response_model=schemas.Category)
def set_category_hidden(
    category_id: str,
    req: CategoryHiddenRequest,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.Category:
    """Hide or unhide a category."""
    _get_or_404(db, category_id)
    db.set_category_hidden(category_id, req.hidden)
    return _to_category(_get_or_404(db, category_id))


@router.delete("/categories/{category_id}", response_model=schemas.MessageResponse)
def delete_category(
    category_id: str,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Delete a category; its transactions fall back to uncategorized."""
    _get_or_404(db, category_id)
    db.delete_category(category_id)
    return schemas.MessageResponse(
        status="ok", message=f"Category {category_id!r} deleted"
    )
