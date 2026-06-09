"""Tests for backend.routers.budget mounted on a fresh FastAPI app.

A temp ``BUD_DB_PATH`` is set BEFORE importing deps so a clean SQLite db is
used (the deps singletons are lru_cached for the process lifetime). The local
budget is seeded with default categories, so GET /budget returns a well-formed
state and assign/move round-trip against real category ids.
"""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_deps_cache():
    """Guarantee the deps lru_caches don't leak a stale (deleted-temp-db) Database
    to later tests, per the CLAUDE.md isolation contract — even if a test's own
    teardown is skipped by an assertion failure."""
    yield
    from backend import deps

    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()


def _build_client_and_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["BUD_DB_PATH"] = db_path

    # Import AFTER setting BUD_DB_PATH so the cached singletons bind to the temp db.
    from backend.deps import get_budget_id, get_db
    from backend.routers import budget

    # Reset any lru_cache state in case deps was imported earlier in the session.
    get_db.cache_clear()
    get_budget_id.cache_clear()
    db = get_db()
    db.ensure_local_budget()

    app = FastAPI()
    app.include_router(budget.router, prefix="/api")
    return TestClient(app), db, db_path


def _seed_income(db, amount: int, month: str) -> None:
    """Give the budget some income (an uncategorized inflow) so there is money
    to assign. Income = uncategorized positive transactions, dated in ``month``.
    """
    from src.cache.database import LOCAL_BUDGET_ID

    db.upsert_transaction(
        txn_id="income-seed", budget_id=LOCAL_BUDGET_ID, account_id=None,
        account_name=None, txn_date=month, amount=amount, memo=None,
        cleared="cleared", approved=True, flag_color=None, payee_id=None,
        payee_name="PAYROLL", category_id=None, category_name=None,
        transfer_account_id=None, transfer_transaction_id=None,
        import_id=None, deleted=False,
    )


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

        # Seed income for the current month so there is money to assign, then
        # re-read so the test sees a positive Ready to Assign.
        _seed_income(db, 100_000, month)
        state = client.get("/api/budget").json()
        assert state["ready_to_assign"] == 100_000

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


def test_assign_over_rta_returns_400():
    """Assigning more than Ready to Assign is rejected with a 400 + detail."""
    client, db, db_path = _build_client_and_db()
    try:
        state = client.get("/api/budget").json()
        month = state["month"]
        c0 = state["categories"][0]["id"]

        _seed_income(db, 100_000, month)

        # Over-assign by one milliunit -> 400, and nothing is written.
        resp = client.post(
            "/api/budget/assign",
            json={"category_id": c0, "amount": 100_001, "month": month},
        )
        assert resp.status_code == 400, resp.text
        assert "100000" in resp.json()["detail"]

        after = client.get("/api/budget").json()
        assert after["ready_to_assign"] == 100_000
        a0 = next(c for c in after["categories"] if c["id"] == c0)
        assert a0["assigned"] == 0  # the rejected assign did not persist

        # Assigning exactly RTA is allowed.
        ok = client.post(
            "/api/budget/assign",
            json={"category_id": c0, "amount": 100_000, "month": month},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["ready_to_assign"] == 0
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)


def test_credit_account_payment_category_auto_appears():
    """GET /budget auto-creates a payment category for a credit account, and
    credit overspend does not dock RTA."""
    client, db, db_path = _build_client_and_db()
    try:
        from src.cache.database import LOCAL_BUDGET_ID

        # A credit account with no payment category yet.
        db.upsert_account("cc1", LOCAL_BUDGET_ID, "Amex", "creditCard",
                          on_budget=True, closed=False, balance=0,
                          cleared_balance=0, uncleared_balance=0)

        state = client.get("/api/budget").json()
        names = {c["name"]: c for c in state["categories"]}
        assert "Amex" in names  # payment category auto-created
        assert names["Amex"]["is_payment"] is True
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)


def test_auto_assign_underfunded_endpoint():
    """POST /budget/auto-assign with the underfunded strategy fills targets."""
    client, db, db_path = _build_client_and_db()
    try:
        from src.cache.database import LOCAL_BUDGET_ID

        cats = client.get("/api/budget").json()["categories"]
        c0 = cats[0]["id"]
        db.upsert_category_target(LOCAL_BUDGET_ID, c0, 50_000,
                                  cadence="monthly", mode="refill")
        # Seed enough income to cover c0's target plus the default seeded
        # non-monthly targets that auto-assign will also fund.
        _seed_income(db, 1_000_000, "2026-06-01")

        resp = client.post(
            "/api/budget/auto-assign",
            json={"strategy": "underfunded", "month": "2026-06-01"},
        )
        assert resp.status_code == 200, resp.text
        state = resp.json()
        target_cat = next(c for c in state["categories"] if c["id"] == c0)
        assert target_cat["assigned"] == 50_000
        assert target_cat["underfunded"] == 0
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)


def test_auto_assign_underfunded_endpoint_respects_rta_guard():
    """Through HTTP: when cash is the binding constraint, auto-assign funds the
    biggest need first and partially fills the rest, never exceeding RTA."""
    client, db, db_path = _build_client_and_db()
    try:
        from src.cache.database import LOCAL_BUDGET_ID

        # Clear the seeded default targets so only our two drive the funding.
        for cid in list(db.get_category_targets(LOCAL_BUDGET_ID)):
            db.delete_category_target(cid)

        cats = client.get("/api/budget").json()["categories"]
        big, small = cats[0]["id"], cats[1]["id"]
        db.upsert_category_target(LOCAL_BUDGET_ID, big, 100_000,
                                  cadence="monthly", mode="refill")
        db.upsert_category_target(LOCAL_BUDGET_ID, small, 40_000,
                                  cadence="monthly", mode="refill")
        # 120k income vs 140k of need -> RTA is the binding constraint.
        _seed_income(db, 120_000, "2026-06-01")

        resp = client.post(
            "/api/budget/auto-assign",
            json={"strategy": "underfunded", "month": "2026-06-01"},
        )
        assert resp.status_code == 200, resp.text
        state = resp.json()
        big_cat = next(c for c in state["categories"] if c["id"] == big)
        small_cat = next(c for c in state["categories"] if c["id"] == small)
        # Biggest need fully funded; the 20k remainder goes to the smaller one.
        assert big_cat["assigned"] == 100_000
        assert small_cat["assigned"] == 20_000
        assert state["ready_to_assign"] == 0
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)


def test_auto_assign_unknown_strategy_400():
    client, db, db_path = _build_client_and_db()
    try:
        resp = client.post(
            "/api/budget/auto-assign", json={"strategy": "bogus"}
        )
        assert resp.status_code == 400, resp.text
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)


def test_assign_into_future_month_drops_current_rta():
    """Assigning into a future month removes the money from the current month's
    RTA, and the furthest assigned month shows the true remaining RTA."""
    client, db, db_path = _build_client_and_db()
    try:
        state = client.get("/api/budget").json()
        c0 = state["categories"][0]["id"]

        # Income lands in June; assign part of it into July (a future month).
        _seed_income(db, 200_000, "2026-06-01")
        resp = client.post(
            "/api/budget/assign",
            json={"category_id": c0, "amount": 80_000, "month": "2026-07-01"},
        )
        assert resp.status_code == 200, resp.text

        june = client.get("/api/budget", params={"month": "2026-06-01"}).json()
        july = client.get("/api/budget", params={"month": "2026-07-01"}).json()
        # June's RTA is reduced by the future-month assignment.
        assert june["ready_to_assign"] == 120_000
        # The furthest assigned month shows the same true remaining RTA.
        assert july["ready_to_assign"] == 120_000
    finally:
        os.environ.pop("BUD_DB_PATH", None)
        if os.path.exists(db_path):
            os.remove(db_path)
