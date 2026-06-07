"""Tests for the categories router (bead bud-66q).

A temp SQLite file is configured via ``BUD_DB_PATH`` BEFORE importing
``backend.deps`` so the shared Database singleton points at it. Only the
categories router is mounted on a fresh FastAPI app, exercising the full
list/create/patch/hide/delete lifecycle.
"""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    os.environ["BUD_DB_PATH"] = str(db_path)

    # Import (and reload) deps/router AFTER setting the env var, and clear the
    # lru_cache-backed singletons so they re-create against the temp DB.
    from backend import deps
    importlib.reload(deps)
    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()

    from backend.routers import categories
    importlib.reload(categories)

    app = FastAPI()
    app.include_router(categories.router, prefix="/api")
    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        deps.get_db.cache_clear()
        deps.get_budget_id.cache_clear()
        os.environ.pop("BUD_DB_PATH", None)
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()


def test_category_lifecycle(client):
    # List seeded defaults (16 of them, see DEFAULT_CATEGORIES).
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    defaults = resp.json()
    assert len(defaults) == 16
    sample = defaults[0]
    assert "id" in sample and "name" in sample
    assert sample["hidden"] is False  # int 0 -> bool coercion

    # Create one.
    resp = client.post(
        "/api/categories", json={"group": "Fun", "name": "Hobbies"}
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Hobbies"
    assert created["category_group_name"] == "Fun"
    assert created["category_group_id"] == "fun"
    assert created["hidden"] is False
    cat_id = created["id"]

    # Patch / rename + regroup.
    resp = client.patch(
        f"/api/categories/{cat_id}",
        json={"name": "Hobbies & Crafts", "group": "Wants"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "Hobbies & Crafts"
    assert updated["category_group_name"] == "Wants"
    assert updated["category_group_id"] == "wants"

    # Hide it.
    resp = client.patch(f"/api/categories/{cat_id}/hidden", json={"hidden": True})
    assert resp.status_code == 200
    assert resp.json()["hidden"] is True

    # Hidden categories are excluded by default, included on request.
    assert all(c["id"] != cat_id for c in client.get("/api/categories").json())
    with_hidden = client.get("/api/categories?include_hidden=true").json()
    assert any(c["id"] == cat_id for c in with_hidden)

    # Unhide.
    resp = client.patch(f"/api/categories/{cat_id}/hidden", json={"hidden": False})
    assert resp.status_code == 200
    assert resp.json()["hidden"] is False

    # Delete it.
    resp = client.delete(f"/api/categories/{cat_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert all(
        c["id"] != cat_id
        for c in client.get("/api/categories?include_hidden=true").json()
    )


def test_404_on_missing_category(client):
    missing = "deadbeef" * 4
    assert client.patch(
        f"/api/categories/{missing}", json={"name": "X", "group": "Y"}
    ).status_code == 404
    assert client.patch(
        f"/api/categories/{missing}/hidden", json={"hidden": True}
    ).status_code == 404
    assert client.delete(f"/api/categories/{missing}").status_code == 404
