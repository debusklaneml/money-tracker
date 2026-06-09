"""End-to-end tests for the local budgeting foundation: import, dedup,
categorization, and the engine's Ready-to-Assign / rollover math."""

import tempfile
from pathlib import Path

import pytest

from src.cache.database import Database, LOCAL_BUDGET_ID, DEFAULT_CATEGORIES
from src.imports.service import ImportService
from src.budget.engine import BudgetEngine, RTAExceededError

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


def _income(db, amount, month, txn_id="inc"):
    """Seed an uncategorized inflow (= income) in ``month`` (YYYY-MM-01)."""
    db.upsert_transaction(
        txn_id=txn_id, budget_id=LOCAL_BUDGET_ID, account_id=None, account_name=None,
        txn_date=month, amount=amount, memo=None, cleared="cleared", approved=True,
        flag_color=None, payee_id=None, payee_name="PAYROLL", category_id=None,
        category_name=None, transfer_account_id=None, transfer_transaction_id=None,
        import_id=None, deleted=False,
    )


def _spend(db, cat_id, cat_name, amount, txn_date, txn_id):
    """Seed a categorized outflow (``amount`` negative) on ``txn_date`` (YYYY-MM-DD)."""
    db.upsert_transaction(
        txn_id=txn_id, budget_id=LOCAL_BUDGET_ID, account_id=None, account_name=None,
        txn_date=txn_date, amount=amount, memo=None, cleared="cleared", approved=True,
        flag_color=None, payee_id=None, payee_name="STORE", category_id=cat_id,
        category_name=cat_name, transfer_account_id=None, transfer_transaction_id=None,
        import_id=None, deleted=False,
    )


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

    # NOTE: updated for the YNAB-correct model. RTA now draws from one cash pool,
    # so the July assignment (100k) reduces June's RTA too — June is 2_100_000,
    # not 2_200_000 (the old per-month-cumulative number). Both months therefore
    # show the same 2_100_000 remaining RTA.
    assert june.ready_to_assign == 2_100_000      # 2500 income - 400 assigned (global)
    assert g_june.available == 180_000            # 300 - 120
    assert july.ready_to_assign == 2_100_000      # 2500 - 400
    assert g_july.available == 230_000            # 400 - 170 (rolls over)
    assert s_july.available == -19_990            # current-month overspend shows red
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


# ---------------------------------------------------------------------------
# YNAB foundation: RTA guard, cash-overspend rollover, future-month assigning
# ---------------------------------------------------------------------------
def test_rta_guard_blocks_over_assign(db):
    """You cannot assign more money than Ready to Assign (income that exists)."""
    _income(db, 100_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)

    # Assigning more than the 100k of income is rejected; nothing is written.
    with pytest.raises(RTAExceededError) as exc:
        eng.assign(groceries, 100_001, month="2026-06-01")
    assert exc.value.available == 100_000
    state = eng.get_state("2026-06-01")
    assert next(c for c in state.categories if c.id == groceries).assigned == 0
    assert state.ready_to_assign == 100_000

    # Assigning exactly RTA is allowed and drives RTA to zero.
    eng.assign(groceries, 100_000, month="2026-06-01")
    assert eng.get_state("2026-06-01").ready_to_assign == 0


def test_rta_guard_allows_reassign_within_existing_assignment(db):
    """Re-setting a category that is already funded must account for the delta,
    not the absolute amount, so lowering or holding an assignment is fine even
    when RTA is exhausted."""
    _income(db, 100_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)
    eng.assign(groceries, 100_000, month="2026-06-01")  # RTA now 0
    # Re-asserting the same amount is a zero delta -> allowed.
    eng.assign(groceries, 100_000, month="2026-06-01")
    # Lowering it frees RTA back up.
    eng.assign(groceries, 60_000, month="2026-06-01")
    assert eng.get_state("2026-06-01").ready_to_assign == 40_000


def test_move_does_not_trip_rta_guard(db):
    """A move is RTA-neutral and must work even when RTA is fully exhausted."""
    _income(db, 100_000, "2026-06-01")
    groceries, gas = _cat(db, "Groceries"), _cat(db, "Gas")
    eng = BudgetEngine(db)
    eng.assign(groceries, 100_000, month="2026-06-01")  # RTA == 0
    # Moving from groceries to gas would briefly look like "assigning" to gas,
    # but the guard must not fire because the net RTA change is zero.
    eng.move(groceries, gas, 30_000, month="2026-06-01")
    state = eng.get_state("2026-06-01")
    assert next(c for c in state.categories if c.id == groceries).assigned == 70_000
    assert next(c for c in state.categories if c.id == gas).assigned == 30_000
    assert state.ready_to_assign == 0  # conserved


def test_cash_overspend_docks_next_month_rta_and_floors_category(db):
    """A prior month's cash overspend does NOT carry a negative category balance
    forward; it floors at 0 and the shortfall is deducted from next month's RTA."""
    _income(db, 100_000, "2026-06-01", txn_id="inc-june")
    _income(db, 100_000, "2026-07-01", txn_id="inc-july")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)

    # June: assign 50k, spend 80k -> overspent by 30k.
    eng.assign(groceries, 50_000, month="2026-06-01")
    _spend(db, groceries, "Groceries", -80_000, "2026-06-15", "g-june")

    june = eng.get_state("2026-06-01")
    g_june = next(c for c in june.categories if c.id == groceries)
    assert g_june.available == -30_000           # current-month overspend shows red
    assert june.ready_to_assign == 50_000        # 100k income - 50k assigned

    # July: the -30k does NOT roll into the category; it floors at 0 and docks
    # July's RTA instead.
    july = eng.get_state("2026-07-01")
    g_july = next(c for c in july.categories if c.id == groceries)
    assert g_july.available == 0                  # floored, not -30k
    # RTA(July) = income_cum 200k - assigned_cum 50k - prior overspend 30k = 120k
    assert july.ready_to_assign == 120_000


def test_cash_overspend_multi_month_accumulates(db):
    """Overspending in two consecutive months docks both shortfalls from RTA,
    and each boundary floors independently."""
    _income(db, 300_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)

    # June overspend 30k, July overspend 10k.
    eng.assign(groceries, 50_000, month="2026-06-01")
    _spend(db, groceries, "Groceries", -80_000, "2026-06-15", "g-june")
    eng.assign(groceries, 20_000, month="2026-07-01")
    _spend(db, groceries, "Groceries", -30_000, "2026-07-15", "g-july")

    aug = eng.get_state("2026-08-01")
    g_aug = next(c for c in aug.categories if c.id == groceries)
    assert g_aug.available == 0
    # assigned_cum = 70k; prior overspends = 30k (June) + 10k (July) = 40k.
    assert aug.ready_to_assign == 300_000 - 70_000 - 40_000  # 190_000


def test_assign_into_future_month_and_furthest_month_rta(db):
    """Money assigned into a future month leaves the current month's RTA and the
    furthest assigned month reports the true remaining RTA; you can assign across
    several future months bounded only by cash."""
    _income(db, 300_000, "2026-06-01")
    groceries, gas, rent = _cat(db, "Groceries"), _cat(db, "Gas"), _cat(db, "Rent / Mortgage")
    eng = BudgetEngine(db)

    eng.assign(groceries, 50_000, month="2026-06-01")   # current month
    eng.assign(gas, 60_000, month="2026-07-01")          # +1 month
    eng.assign(rent, 90_000, month="2026-08-01")         # +2 months

    june = eng.get_state("2026-06-01")
    july = eng.get_state("2026-07-01")
    aug = eng.get_state("2026-08-01")

    # June's RTA already reflects every future assignment (cumulative model).
    assert june.ready_to_assign == 300_000 - (50_000 + 60_000 + 90_000)  # 100_000
    # The furthest assigned month shows the same true remaining RTA.
    assert aug.ready_to_assign == 100_000
    assert july.ready_to_assign == 100_000

    # Cannot assign beyond the remaining 100k cash, even far in the future.
    with pytest.raises(RTAExceededError):
        eng.assign(gas, 100_001, month="2026-12-01")
    # But assigning exactly the remaining cash far ahead is fine.
    eng.assign(gas, 100_000, month="2026-12-01")
    assert eng.get_state("2026-12-01").ready_to_assign == 0
