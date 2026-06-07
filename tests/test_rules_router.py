"""Tests for the rules router (bead bud-37w).

A temp SQLite file is configured via ``BUD_DB_PATH`` BEFORE importing
``backend.deps`` so the shared Database singleton points at it. Only the rules
router is mounted on a fresh FastAPI app, exercising the full
create/list/apply/delete lifecycle plus 404s.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def setup():
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

    from backend.routers import rules

    app = FastAPI()
    app.include_router(rules.router, prefix="/api")

    db = deps.get_db()
    budget_id = deps.get_budget_id()

    # Pick a real seeded category to assign via the rule.
    category = db.get_categories(budget_id)[0]

    # An uncategorized transaction whose payee matches our pattern.
    db.upsert_transaction(
        "txn-coffee", budget_id, "acct-1", "Checking", "2026-01-06", -1200,
        "morning", "cleared", True, None, None, "Coffee Shop Downtown",
        None, None, None, None, "imp-1", False,
    )

    test_client = TestClient(app)
    try:
        yield test_client, db, budget_id, category
    finally:
        deps.get_db.cache_clear()
        deps.get_budget_id.cache_clear()
        os.environ.pop("BUD_DB_PATH", None)
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()


def test_rule_lifecycle(setup):
    client, db, budget_id, category = setup

    # No rules to start.
    resp = client.get("/api/rules")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create a rule matching the seeded transaction's payee.
    resp = client.post(
        "/api/rules",
        json={"pattern": "Coffee", "category_id": category["id"]},
    )
    assert resp.status_code == 201
    created = resp.json()
    rule_id = created["id"]
    assert created["pattern"] == "Coffee"
    assert created["category_id"] == category["id"]
    assert created["match_field"] == "payee"
    assert created["match_type"] == "contains"
    # Joined columns are present on the response.
    assert created["category_name"] == category["name"]
    assert created["group_name"] == category["category_group_name"]

    # List shows the new rule with its joined fields.
    listed = client.get("/api/rules").json()
    assert len(listed) == 1
    assert listed[0]["id"] == rule_id
    assert listed[0]["category_name"] == category["name"]
    assert listed[0]["group_name"] == category["category_group_name"]

    # Apply it: the matching uncategorized txn gets categorized.
    resp = client.post(f"/api/rules/{rule_id}/apply")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "1" in body["message"]
    # Confirm the transaction actually got the category.
    txn = next(t for t in db.get_transactions(budget_id) if t["id"] == "txn-coffee")
    assert txn["category_id"] == category["id"]
    assert txn["category_name"] == category["name"]

    # Delete it.
    resp = client.delete(f"/api/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert client.get("/api/rules").json() == []

    # Deleting again is a 404.
    assert client.delete(f"/api/rules/{rule_id}").status_code == 404


def test_create_rule_unknown_category_is_400(setup):
    client, db, budget_id, category = setup
    resp = client.post(
        "/api/rules",
        json={"pattern": "X", "category_id": "deadbeef" * 4},
    )
    assert resp.status_code == 400


def test_apply_and_delete_unknown_rule_are_404(setup):
    client, db, budget_id, category = setup
    assert client.post("/api/rules/99999/apply").status_code == 404
    assert client.delete("/api/rules/99999").status_code == 404
