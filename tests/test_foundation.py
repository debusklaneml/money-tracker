"""End-to-end tests for the local budgeting foundation: import, dedup,
categorization, and the engine's Ready-to-Assign / rollover math."""

import tempfile
from pathlib import Path

import pytest

from src.cache.database import Database, LOCAL_BUDGET_ID, DEFAULT_CATEGORIES
from src.imports.service import ImportService
from src.budget.engine import BudgetEngine

OFX = """OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKACCTFROM><ACCTID>9988<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260603<TRNAMT>2500.00<FITID>P1<NAME>ACME PAYROLL</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260610<TRNAMT>-120.00<FITID>G1<NAME>WHOLE FOODS</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260705<TRNAMT>-50.00<FITID>G2<NAME>TRADER JOES</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260712<TRNAMT>-19.99<FITID>N1<NAME>NETFLIX</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>2310.01<DTASOF>20260712</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


@pytest.fixture
def db():
    return Database(Path(tempfile.mkdtemp()) / "t.db")


def _cat(db, name):
    return next(c for c in db.get_categories(LOCAL_BUDGET_ID) if c["name"] == name)["id"]


def test_default_categories_seeded(db):
    assert len(db.get_categories(LOCAL_BUDGET_ID)) == len(DEFAULT_CATEGORIES)


def test_import_and_dedup(db):
    svc = ImportService(db)
    r = svc.import_file("june.qfx", OFX.encode())
    assert r.imported == 4
    assert "Checking" in r.accounts[0]
    again = svc.import_file("june.qfx", OFX.encode())
    assert again.imported == 0 and again.duplicates == 4


def test_income_is_uncategorized_inflow(db):
    ImportService(db).import_file("june.qfx", OFX.encode())
    assert db.income_total(LOCAL_BUDGET_ID, "2026-12-01") == 2_500_000
    assert db.count_uncategorized(LOCAL_BUDGET_ID) == 4


def test_rule_autocategorizes(db):
    svc = ImportService(db)
    svc.import_file("june.qfx", OFX.encode())
    rid = db.add_rule(LOCAL_BUDGET_ID, "NETFLIX", _cat(db, "Subscriptions"))
    assert svc.apply_rule_to_existing(rid) == 1


def test_engine_rta_rollover_and_overspend(db):
    svc = ImportService(db)
    svc.import_file("june.qfx", OFX.encode())
    groceries, subs = _cat(db, "Groceries"), _cat(db, "Subscriptions")
    for t in db.get_uncategorized_transactions(LOCAL_BUDGET_ID):
        if t["payee_name"] in ("WHOLE FOODS", "TRADER JOES"):
            db.set_transaction_category(t["id"], groceries, "Groceries")
        elif t["payee_name"] == "NETFLIX":
            db.set_transaction_category(t["id"], subs, "Subscriptions")

    eng = BudgetEngine(db)
    eng.assign(groceries, 300_000, month="2026-06-01")
    eng.assign(groceries, 100_000, month="2026-07-01")

    june = eng.get_state("2026-06-01")
    july = eng.get_state("2026-07-01")
    g_june = next(c for c in june.categories if c.id == groceries)
    g_july = next(c for c in july.categories if c.id == groceries)
    s_july = next(c for c in july.categories if c.id == subs)

    assert june.ready_to_assign == 2_200_000      # 2500 income - 300 assigned
    assert g_june.available == 180_000            # 300 - 120
    assert july.ready_to_assign == 2_100_000      # 2500 - 400
    assert g_july.available == 230_000            # 400 - 170 (rolls over)
    assert s_july.available == -19_990            # overspent
    assert any(c.id == subs for c in july.overspent)


def test_move_money_covers_overspend(db):
    svc = ImportService(db)
    svc.import_file("june.qfx", OFX.encode())
    groceries, subs = _cat(db, "Groceries"), _cat(db, "Subscriptions")
    for t in db.get_uncategorized_transactions(LOCAL_BUDGET_ID):
        if t["payee_name"] == "NETFLIX":
            db.set_transaction_category(t["id"], subs, "Subscriptions")
    eng = BudgetEngine(db)
    eng.assign(groceries, 300_000, month="2026-07-01")
    eng.move(groceries, subs, 20_000, month="2026-07-01")
    july = eng.get_state("2026-07-01")
    assert next(c for c in july.categories if c.id == subs).available == 10  # -19990 + 20000
