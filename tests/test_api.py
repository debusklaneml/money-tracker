"""End-to-end API tests (bead bud-8u2).

Exercises the FULLY-ASSEMBLED app (``backend.main.app`` with every router
mounted under ``/api``) through one realistic flow:

    upload OFX  ->  categorize a txn  ->  assign budget  ->  GET /api/budget
    (asserts Ready-to-Assign and cross-month rollover)  ->  re-import (dedup).

A temp SQLite file is wired via ``BUD_DB_PATH`` BEFORE the backend modules are
imported so the shared Database singleton points at it. The lru_cache'd
providers are cleared around the test so the temp db is built fresh. We do NOT
reload modules: that would swap their identity in ``sys.modules`` and break the
sibling router tests that rely on stable module references.

The sample statement (reused from the imports-router test) carries:
  * Coffee Shop  -25.00  on 2026-01-01  (an expense, initially uncategorized)
  * Employer    +1500.00 on 2026-01-03  (an uncategorized inflow == income)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

JAN = "2026-01-01"
FEB = "2026-02-01"

# Minimal valid OFX 1.x (SGML): one checking account, one expense + one income.
SAMPLE_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<ACCTID>123456789
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260101120000
<TRNAMT>-25.00
<FITID>TXN-0001
<NAME>Coffee Shop
<MEMO>Latte
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260103120000
<TRNAMT>1500.00
<FITID>TXN-0002
<NAME>Employer
<MEMO>Paycheck
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>1475.00
<DTASOF>20260103120000
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

@pytest.fixture()
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    os.environ["BUD_DB_PATH"] = str(db_path)

    # Import (not reload) so module identity stays stable for sibling tests.
    # The assembled app's routers Depends() on these same provider objects.
    from backend import deps
    import backend.main as main

    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()

    test_client = TestClient(main.app)
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


def _upload(client, path, content=SAMPLE_OFX, filename="statement.ofx"):
    return client.post(
        path, files={"file": (filename, content, "application/x-ofx")}
    )


def _cat(state, category_id):
    """Find a category's state within a BudgetState response by id."""
    for c in state["categories"]:
        if c["id"] == category_id:
            return c
    raise AssertionError(f"category {category_id} not in budget state")


def test_full_flow_import_categorize_assign_rollover_dedup(client):
    # --- 1. Import the statement ------------------------------------------
    resp = _upload(client, "/api/imports")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["imported"] == 2
    assert result["duplicates"] == 0
    assert result["already_imported_file"] is False

    # One account created from the statement.
    accounts = client.get("/api/accounts").json()
    assert len(accounts) == 1

    # Both transactions land uncategorized.
    txns = client.get("/api/transactions").json()
    assert len(txns) == 2
    coffee = next(t for t in txns if t["amount"] == -25000)
    paycheck = next(t for t in txns if t["amount"] == 1500000)
    assert coffee["category_id"] is None
    assert paycheck["category_id"] is None

    # --- 2. Budget before any assignment: paycheck is income, RTA == income
    state = client.get(f"/api/budget?month={JAN}").json()
    assert state["income_month"] == 1500000
    assert state["income_total"] == 1500000
    assert state["assigned_total"] == 0
    assert state["ready_to_assign"] == 1500000  # nothing assigned yet

    # Pick a real category to categorize the coffee into.
    categories = client.get("/api/categories").json()
    assert categories, "expected seeded default categories"
    target = categories[0]
    target_id = target["id"]

    # --- 3. Categorize the coffee expense ---------------------------------
    patch = client.patch(
        f"/api/transactions/{coffee['id']}",
        json={"category_id": target_id, "category_name": target["name"]},
    )
    assert patch.status_code == 200, patch.text

    # Activity now shows on the category; spending does NOT reduce RTA.
    state = client.get(f"/api/budget?month={JAN}").json()
    cat = _cat(state, target_id)
    assert cat["activity"] == -25000
    assert cat["assigned"] == 0
    assert cat["available"] == -25000  # overspent: assigned 0 + activity -25000
    assert state["ready_to_assign"] == 1500000  # unchanged by spending

    # --- 4. Assign $50 to the category for January ------------------------
    assigned = client.post(
        "/api/budget/assign",
        json={"category_id": target_id, "amount": 50000, "month": JAN},
    )
    assert assigned.status_code == 200, assigned.text
    state = assigned.json()  # endpoint returns the fresh state for that month
    assert state["assigned_total"] == 50000
    assert state["ready_to_assign"] == 1450000  # 1_500_000 - 50_000
    cat = _cat(state, target_id)
    assert cat["assigned"] == 50000
    assert cat["activity"] == -25000
    assert cat["available"] == 25000  # 50_000 assigned - 25_000 spent

    # --- 5. Rollover: February inherits the leftover available ------------
    feb = client.get(f"/api/budget?month={FEB}").json()
    cat_feb = _cat(feb, target_id)
    assert cat_feb["assigned"] == 0  # nothing assigned *this* month
    assert cat_feb["activity"] == 0  # no February activity
    assert cat_feb["available"] == 25000  # rolled forward from January
    assert feb["ready_to_assign"] == 1450000  # cumulative, unchanged

    # --- 6. Re-import the same file: full dedup, nothing added ------------
    resp2 = _upload(client, "/api/imports")
    assert resp2.status_code == 200, resp2.text
    result2 = resp2.json()
    assert result2["imported"] == 0
    assert result2["duplicates"] == 2
    assert result2["already_imported_file"] is True

    # Transaction count is still two; the categorization survived re-import.
    txns_after = client.get("/api/transactions").json()
    assert len(txns_after) == 2
    coffee_after = next(t for t in txns_after if t["amount"] == -25000)
    assert coffee_after["category_id"] == target_id


def test_move_between_categories(client):
    """POST /api/budget/move shifts assigned money without touching RTA."""
    _upload(client, "/api/imports")
    categories = client.get("/api/categories").json()
    src, dst = categories[0], categories[1]

    # Fund the source category, then move half to the destination.
    client.post(
        "/api/budget/assign",
        json={"category_id": src["id"], "amount": 40000, "month": JAN},
    )
    moved = client.post(
        "/api/budget/move",
        json={"from_id": src["id"], "to_id": dst["id"], "amount": 15000, "month": JAN},
    )
    assert moved.status_code == 200, moved.text
    state = moved.json()
    assert _cat(state, src["id"])["assigned"] == 25000
    assert _cat(state, dst["id"])["assigned"] == 15000
    # Total assigned (and therefore RTA) is conserved by a move.
    assert state["assigned_total"] == 40000
    assert state["ready_to_assign"] == 1500000 - 40000


def test_settings_summary_reflects_state(client):
    """The settings summary aggregates counts across the assembled app."""
    _upload(client, "/api/imports")
    summary = client.get("/api/settings/summary").json()
    assert summary["account_count"] == 1
    assert summary["transaction_count"] == 2
    assert summary["category_count"] >= 1
    assert "ready_to_assign" in summary
    assert "db_path" in summary

    # clear-data wipes imported rows but keeps the category structure.
    cleared = client.post("/api/settings/clear-data")
    assert cleared.status_code == 200, cleared.text
    after = client.get("/api/settings/summary").json()
    assert after["transaction_count"] == 0
    assert after["account_count"] == 0
    assert after["category_count"] == summary["category_count"]
