"""Tests for the transactions router (bead bud-avj).

These exercise the router end-to-end via FastAPI's TestClient against a real,
temporary SQLite database. ``BUD_DB_PATH`` is set BEFORE importing ``backend``
so the dependency providers (which cache a single Database keyed off that env
var) point at the temp file. The lru_cache'd providers are cleared in fixture
teardown so each module run is isolated.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def client():
    tmp = Path(tempfile.mkdtemp()) / "test_txn.db"
    os.environ["BUD_DB_PATH"] = str(tmp)

    # Import AFTER setting the env var so providers pick up the temp path.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend import deps
    from backend.routers import transactions

    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()

    app = FastAPI()
    app.include_router(transactions.router, prefix="/api")

    db = deps.get_db()
    budget_id = deps.get_budget_id()

    # Pick a real category to categorize into.
    category = db.get_categories(budget_id)[0]

    # Two accounts' worth of transactions: one already categorized, two not.
    db.upsert_transaction(
        "txn-cat", budget_id, "acct-1", "Checking", "2026-01-05", -5000,
        "lunch", "cleared", True, None, None, "Cafe Payee",
        category["id"], category["name"], None, None, "imp-1", False,
    )
    db.upsert_transaction(
        "txn-unc-1", budget_id, "acct-1", "Checking", "2026-01-06", -1200,
        "coffee", "cleared", True, None, None, "Coffee Shop",
        None, None, None, None, "imp-2", False,
    )
    db.upsert_transaction(
        "txn-unc-2", budget_id, "acct-2", "Savings", "2026-01-07", -9900,
        "gizmo", "uncleared", True, None, None, "Gadget Store",
        None, None, None, None, "imp-3", False,
    )

    yield TestClient(app), db, budget_id, category

    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()
    os.environ.pop("BUD_DB_PATH", None)
    for p in (tmp, Path(str(tmp) + "-wal"), Path(str(tmp) + "-shm")):
        if p.exists():
            p.unlink()


def test_list_all(client):
    tc, _db, _bid, _cat = client
    resp = tc.get("/api/transactions")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert ids == {"txn-cat", "txn-unc-1", "txn-unc-2"}


def test_list_account_filter(client):
    tc, _db, _bid, _cat = client
    resp = tc.get("/api/transactions", params={"account_id": "acct-2"})
    assert resp.status_code == 200
    body = resp.json()
    assert [t["id"] for t in body] == ["txn-unc-2"]


def test_list_search_filter(client):
    tc, _db, _bid, _cat = client
    resp = tc.get("/api/transactions", params={"search": "coffee"})
    assert resp.status_code == 200
    # "coffee" matches memo of unc-1 and payee_name "Coffee Shop" of unc-1.
    assert [t["id"] for t in resp.json()] == ["txn-unc-1"]


def test_list_uncategorized_flag(client):
    tc, _db, _bid, _cat = client
    resp = tc.get("/api/transactions", params={"uncategorized": "true"})
    assert resp.status_code == 200
    assert {t["id"] for t in resp.json()} == {"txn-unc-1", "txn-unc-2"}


def test_uncategorized_route_and_count(client):
    tc, _db, _bid, _cat = client
    resp = tc.get("/api/transactions/uncategorized")
    assert resp.status_code == 200
    assert {t["id"] for t in resp.json()} == {"txn-unc-1", "txn-unc-2"}

    count = tc.get("/api/transactions/uncategorized/count")
    assert count.status_code == 200
    assert count.json() == 2


def test_categorize_resolves_name(client):
    tc, db, _bid, cat = client
    # Provide only the id; the router should resolve the name.
    resp = tc.patch("/api/transactions/txn-unc-1", json={"category_id": cat["id"]})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Verify via the uncategorized count dropping and the stored name.
    assert db.count_uncategorized(_bid) == 1
    txn = next(
        r for r in db.get_transactions(_bid) if r["id"] == "txn-unc-1"
    )
    assert txn["category_id"] == cat["id"]
    assert txn["category_name"] == cat["name"]


def test_bulk_categorize(client):
    tc, db, bid, cat = client
    resp = tc.post(
        "/api/transactions/bulk-categorize",
        json={
            "transaction_ids": ["txn-unc-1", "txn-unc-2"],
            "category_id": cat["id"],
        },
    )
    assert resp.status_code == 200
    assert "2" in resp.json()["message"]
    assert db.count_uncategorized(bid) == 0
    for tid in ("txn-unc-1", "txn-unc-2"):
        txn = next(r for r in db.get_transactions(bid) if r["id"] == tid)
        assert txn["category_id"] == cat["id"]
        assert txn["category_name"] == cat["name"]


def test_categorize_clear(client):
    tc, db, bid, _cat = client
    # Clearing: null id -> name forced null, becomes uncategorized.
    resp = tc.patch(
        "/api/transactions/txn-cat", json={"category_id": None, "category_name": None}
    )
    assert resp.status_code == 200
    txn = next(r for r in db.get_transactions(bid) if r["id"] == "txn-cat")
    assert txn["category_id"] is None
    assert txn["category_name"] is None
