"""Tests for backend.routers.budget mounted on a fresh FastAPI app.

A temp ``BUD_DB_PATH`` is set BEFORE importing deps so a clean SQLite db is
used (the deps singletons are lru_cached for the process lifetime). The local
budget is seeded with default categories, so GET /budget returns a well-formed
state and assign/move round-trip against real category ids.
"""

import os
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_client_and_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["BUD_DB_PATH"] = db_path

    # Import AFTER setting BUD_DB_PATH so the cached singletons bind to the temp db.
    from backend.deps import get_db
    from backend.routers import budget

    # Reset any lru_cache state in case deps was imported earlier in the session.
    get_db.cache_clear()
    db = get_db()
    db.ensure_local_budget()

    app = FastAPI()
    app.include_router(budget.router, prefix="/api")
    return TestClient(app), db, db_path


def test_budget_router_roundtrip():
    client, db, db_path = _build_client_and_db()
    try:
        # GET /budget -> 200 + well-formed state
        resp = client.get("/api/budget")
        assert resp.status_code == 200, resp.text
        state = resp.json()
        for key in (
            "month",
            "ready_to_assign",
            "income_month",
            "income_total",
            "assigned_total",
            "categories",
        ):
            assert key in state
        assert isinstance(state["categories"], list)
        assert len(state["categories"]) >= 2  # default seed categories exist

        month = state["month"]
        cats = state["categories"]
        c0, c1 = cats[0]["id"], cats[1]["id"]

        # POST /budget/assign -> updated state reflects the assignment
        resp = client.post(
            "/api/budget/assign",
            json={"category_id": c0, "amount": 50_000, "month": month},
        )
        assert resp.status_code == 200, resp.text
        after_assign = resp.json()
        a0 = next(c for c in after_assign["categories"] if c["id"] == c0)
        assert a0["assigned"] == 50_000
        assert a0["available"] == 50_000
        assert after_assign["assigned_total"] == 50_000

        # POST /budget/move -> 20_000 from c0 to c1
        resp = client.post(
            "/api/budget/move",
            json={"from_id": c0, "to_id": c1, "amount": 20_000, "month": month},
        )
        assert resp.status_code == 200, resp.text
        after_move = resp.json()
        m0 = next(c for c in after_move["categories"] if c["id"] == c0)
        m1 = next(c for c in after_move["categories"] if c["id"] == c1)
        assert m0["assigned"] == 30_000
        assert m1["assigned"] == 20_000
        # Total assigned is conserved by a move.
        assert after_move["assigned_total"] == 50_000

        # GET with explicit month query param still works.
        resp = client.get("/api/budget", params={"month": month})
        assert resp.status_code == 200
        assert resp.json()["month"] == month
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)
