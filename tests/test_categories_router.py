"""Tests for the categories router (bead bud-66q).

A temp SQLite file is configured via ``BUD_DB_PATH`` BEFORE importing
``backend.deps`` so the shared Database singleton points at it. Only the
categories router is mounted on a fresh FastAPI app, exercising the full
list/create/patch/hide/delete lifecycle.
"""

from __future__ import annotations

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

    # Import deps/router AFTER setting the env var, and clear the
    # lru_cache-backed singletons so they re-create against the temp DB.
    # (No importlib.reload: reloading swaps module identity in sys.modules,
    # which desyncs routers' Depends() from the providers other tests clear.)
    from backend import deps
    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()

    from backend.routers import categories

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
    # List seeded defaults (see DEFAULT_CATEGORIES).
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    defaults = resp.json()
    from src.cache.database import DEFAULT_CATEGORIES
    assert len(defaults) == len(DEFAULT_CATEGORIES)
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


def test_category_target_lifecycle(client):
    cats = client.get("/api/categories").json()
    cat_id = cats[0]["id"]

    # No target initially.
    assert client.get(f"/api/categories/{cat_id}/target").status_code == 404

    # Set a monthly refill target.
    resp = client.put(
        f"/api/categories/{cat_id}/target",
        json={"amount_milliunits": 50_000, "cadence": "monthly", "mode": "refill"},
    )
    assert resp.status_code == 200, resp.text
    t = resp.json()
    assert t["amount_milliunits"] == 50_000
    assert t["cadence"] == "monthly"
    assert t["mode"] == "refill"
    assert t["category_id"] == cat_id

    # Read it back.
    got = client.get(f"/api/categories/{cat_id}/target").json()
    assert got["amount_milliunits"] == 50_000

    # Replace with a custom every-3-months full target.
    resp = client.put(
        f"/api/categories/{cat_id}/target",
        json={
            "amount_milliunits": 90_000, "cadence": "custom",
            "mode": "full", "every_n_months": 3,
        },
    )
    assert resp.json()["every_n_months"] == 3
    assert resp.json()["mode"] == "full"

    # Delete it.
    assert client.delete(f"/api/categories/{cat_id}/target").status_code == 200
    assert client.get(f"/api/categories/{cat_id}/target").status_code == 404


def test_404_on_missing_category(client):
    missing = "deadbeef" * 4
    assert client.patch(
        f"/api/categories/{missing}", json={"name": "X", "group": "Y"}
    ).status_code == 404
    assert client.patch(
        f"/api/categories/{missing}/hidden", json={"hidden": True}
    ).status_code == 404
    assert client.delete(f"/api/categories/{missing}").status_code == 404
    # The target endpoints guard the parent category too.
    assert client.get(f"/api/categories/{missing}/target").status_code == 404
    assert client.put(
        f"/api/categories/{missing}/target",
        json={"amount_milliunits": 1000, "cadence": "monthly", "mode": "refill"},
    ).status_code == 404
    assert client.delete(f"/api/categories/{missing}/target").status_code == 404


def test_invalid_target_cadence_or_mode_rejected(client):
    cat_id = client.get("/api/categories").json()[0]["id"]
    # Unknown cadence / mode / non-positive amount -> 422 (not silently stored).
    assert client.put(
        f"/api/categories/{cat_id}/target",
        json={"amount_milliunits": 1000, "cadence": "daily", "mode": "refill"},
    ).status_code == 422
    assert client.put(
        f"/api/categories/{cat_id}/target",
        json={"amount_milliunits": 1000, "cadence": "monthly", "mode": "bogus"},
    ).status_code == 422
    assert client.put(
        f"/api/categories/{cat_id}/target",
        json={"amount_milliunits": 0, "cadence": "monthly", "mode": "refill"},
    ).status_code == 422


def test_delete_category_removes_its_target(client):
    """Deleting a category must not leave an orphan row in category_targets."""
    from backend import deps

    db = deps.get_db()
    cat_id = client.get("/api/categories").json()[0]["id"]
    assert client.put(
        f"/api/categories/{cat_id}/target",
        json={"amount_milliunits": 50_000, "cadence": "monthly", "mode": "refill"},
    ).status_code == 200
    assert db.get_category_target(cat_id) is not None

    assert client.delete(f"/api/categories/{cat_id}").status_code == 200
    assert db.get_category_target(cat_id) is None
