"""Tests for the accounts / insights / alerts / settings routers (bead bud-bo5).

A temp SQLite file is configured via ``BUD_DB_PATH`` BEFORE importing
``backend.deps`` so the shared Database singleton points at it. All four routers
are mounted on a fresh FastAPI app under ``/api``. The DB is seeded directly via
the Database API (a category + a few transactions + an account) so the endpoints
have something to report.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def ctx():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    os.environ["BUD_DB_PATH"] = str(db_path)

    # No importlib.reload: reloading swaps module identity in sys.modules,
    # which desyncs routers' Depends() from the providers other tests clear.
    from backend import deps
    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()

    from backend.routers import accounts, alerts, insights, settings

    app = FastAPI()
    app.include_router(accounts.router, prefix="/api")
    app.include_router(insights.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    client = TestClient(app)

    db = deps.get_db()
    budget_id = deps.get_budget_id()

    try:
        yield client, db, budget_id
    finally:
        deps.get_db.cache_clear()
        deps.get_budget_id.cache_clear()
        os.environ.pop("BUD_DB_PATH", None)
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()


def _seed(db, budget_id):
    """Seed one account, one category and a few outflow transactions."""
    acct_id = uuid.uuid4().hex
    db.upsert_account(
        account_id=acct_id,
        budget_id=budget_id,
        name="Checking",
        account_type="checking",
        on_budget=True,
        closed=False,
        balance=100000,
        cleared_balance=100000,
        uncleared_balance=0,
    )

    cat_id = db.create_category(budget_id, "Bills", "Groceries")
    cat_row = db.get_category(cat_id)
    cat_name = cat_row["name"]

    today = date.today()
    for i in range(3):
        db.upsert_transaction(
            txn_id=uuid.uuid4().hex,
            budget_id=budget_id,
            account_id=acct_id,
            account_name="Checking",
            txn_date=(today - timedelta(days=i)).isoformat(),
            amount=-(1000 * (i + 1)),
            memo=f"txn {i}",
            cleared="cleared",
            approved=True,
            flag_color=None,
            payee_id=None,
            payee_name=f"Store {i}",
            category_id=cat_id,
            category_name=cat_name,
            transfer_account_id=None,
            transfer_transaction_id=None,
            import_id=None,
            deleted=False,
        )
    return acct_id, cat_id


def test_misc_routers(ctx):
    client, db, budget_id = ctx
    acct_id, cat_id = _seed(db, budget_id)

    # --- accounts ---
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) == 1
    acct = accounts[0]
    assert acct["id"] == acct_id
    assert acct["name"] == "Checking"
    assert acct["on_budget"] is True  # int 1 -> bool
    assert acct["closed"] is False

    # --- insights: spending-by-category ---
    resp = client.get("/api/insights/spending-by-category", params={"months": 1})
    assert resp.status_code == 200
    sbc = resp.json()
    assert len(sbc) == 1
    row = sbc[0]
    assert row["category_id"] == cat_id
    assert row["transaction_count"] == 3
    assert row["total_amount"] == 1000 + 2000 + 3000  # ABS sum of outflows
    assert set(row.keys()) >= {"category_id", "category_name", "total_amount", "transaction_count"}

    # --- insights: monthly-trend ---
    resp = client.get("/api/insights/monthly-trend", params={"months": 12})
    assert resp.status_code == 200
    trend = resp.json()
    assert len(trend) >= 1
    pt = trend[0]
    assert set(pt.keys()) == {"month", "total_amount"}
    assert isinstance(pt["month"], str)
    assert sum(p["total_amount"] for p in trend) == 6000

    # --- alerts: run detection ---
    resp = client.post("/api/alerts/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    # --- alerts: list (count >= 0; minimal seed may produce zero) ---
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    assert isinstance(alerts, list)

    # dismiss/ack: only if detection produced an alert with a persisted id.
    if alerts:
        alert_id = alerts[0]["id"]
        # metadata must be a dict or None (json-decoded), never a raw string.
        assert alerts[0]["metadata"] is None or isinstance(alerts[0]["metadata"], dict)
        resp = client.post(f"/api/alerts/{alert_id}/acknowledge")
        assert resp.status_code == 200
        resp = client.post(f"/api/alerts/{alert_id}/dismiss")
        assert resp.status_code == 200
    else:
        # Best-effort endpoints still return 200 for a non-existent id.
        resp = client.post("/api/alerts/999999/acknowledge")
        assert resp.status_code == 200
        resp = client.post("/api/alerts/999999/dismiss")
        assert resp.status_code == 200

    # --- settings: summary ---
    resp = client.get("/api/settings/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["account_count"] == 1
    assert summary["category_count"] >= 1  # seeded defaults + Groceries
    assert summary["transaction_count"] == 3
    assert summary["rule_count"] == 0
    assert isinstance(summary["active_alert_count"], int)
    assert summary["current_month"].endswith("-01")
    assert isinstance(summary["ready_to_assign"], int)
    assert summary["db_path"]

    # --- settings: clear-data (destructive) ---
    resp = client.post("/api/settings/clear-data")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # transactions + accounts gone, categories remain.
    assert client.get("/api/accounts").json() == []
    assert client.get("/api/settings/summary").json()["transaction_count"] == 0
    assert client.get("/api/settings/summary").json()["category_count"] >= 1
