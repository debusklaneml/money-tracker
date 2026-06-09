"""Credit-card handling (bud-px9).

Proves the YNAB credit-card semantics through the engine:
  (a) cash overspend still docks Ready to Assign;
  (b) credit overspend does NOT dock RTA and increases the card's payment
      category need/debt.
"""

import tempfile
from pathlib import Path

import pytest

from src.cache.database import Database, LOCAL_BUDGET_ID
from src.budget.engine import BudgetEngine


@pytest.fixture
def db():
    return Database(Path(tempfile.mkdtemp()) / "t.db")


def _cat(db, name):
    return next(c for c in db.get_categories(LOCAL_BUDGET_ID) if c["name"] == name)["id"]


def _income(db, amount, month, txn_id="inc"):
    db.upsert_transaction(
        txn_id=txn_id, budget_id=LOCAL_BUDGET_ID, account_id=None, account_name=None,
        txn_date=month, amount=amount, memo=None, cleared="cleared", approved=True,
        flag_color=None, payee_id=None, payee_name="PAYROLL", category_id=None,
        category_name=None, transfer_account_id=None, transfer_transaction_id=None,
        import_id=None, deleted=False,
    )


def _spend(db, account_id, cat_id, cat_name, amount, txn_date, txn_id):
    db.upsert_transaction(
        txn_id=txn_id, budget_id=LOCAL_BUDGET_ID, account_id=account_id,
        account_name=None, txn_date=txn_date, amount=amount, memo=None,
        cleared="cleared", approved=True, flag_color=None, payee_id=None,
        payee_name="STORE", category_id=cat_id, category_name=cat_name,
        transfer_account_id=None, transfer_transaction_id=None, import_id=None,
        deleted=False,
    )


def _checking(db):
    db.upsert_account("acct-chk", LOCAL_BUDGET_ID, "Checking", "checking",
                      on_budget=True, closed=False, balance=0,
                      cleared_balance=0, uncleared_balance=0)
    return "acct-chk"


def _credit(db):
    db.upsert_account("acct-cc", LOCAL_BUDGET_ID, "Visa", "creditCard",
                      on_budget=True, closed=False, balance=0,
                      cleared_balance=0, uncleared_balance=0)
    db.sync_payment_categories(LOCAL_BUDGET_ID)
    return "acct-cc"


def test_credit_account_gets_payment_category(db):
    _credit(db)
    pay = db.get_payment_category_for_account(LOCAL_BUDGET_ID, "acct-cc")
    assert pay is not None
    assert pay["name"] == "Visa"
    assert pay["category_group_name"] == "Credit Card Payments"
    # Idempotent: syncing again does not create a second one.
    db.sync_payment_categories(LOCAL_BUDGET_ID)
    pays = [c for c in db.get_categories(LOCAL_BUDGET_ID)
            if c["payment_account_id"] == "acct-cc"]
    assert len(pays) == 1


def test_cash_overspend_still_docks_rta(db):
    """Baseline (a): overspending on a CASH account still docks next month RTA."""
    chk = _checking(db)
    _income(db, 100_000, "2026-06-01", txn_id="inc-jun")
    _income(db, 100_000, "2026-07-01", txn_id="inc-jul")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)

    eng.assign(groceries, 50_000, month="2026-06-01")
    _spend(db, chk, groceries, "Groceries", -80_000, "2026-06-15", "g-jun")

    july = eng.get_state("2026-07-01")
    g = next(c for c in july.categories if c.id == groceries)
    assert g.available == 0  # floored
    # RTA July = 200k income - 50k assigned - 30k prior cash overspend.
    assert july.ready_to_assign == 120_000


def test_credit_overspend_does_not_dock_rta_and_grows_payment(db):
    """(b): overspending on a CREDIT card does NOT dock RTA; it becomes debt and
    raises the card's payment-category need."""
    cc = _credit(db)
    _income(db, 100_000, "2026-06-01", txn_id="inc-jun")
    _income(db, 100_000, "2026-07-01", txn_id="inc-jul")
    groceries = _cat(db, "Groceries")
    pay_id = db.get_payment_category_for_account(LOCAL_BUDGET_ID, cc)["id"]
    eng = BudgetEngine(db)

    # Assign 50k to groceries, then spend 80k on the credit card -> overspent 30k,
    # but it's all credit, so it must NOT dock RTA.
    eng.assign(groceries, 50_000, month="2026-06-01")
    _spend(db, cc, groceries, "Groceries", -80_000, "2026-06-15", "g-jun")

    june = eng.get_state("2026-06-01")
    g_june = next(c for c in june.categories if c.id == groceries)
    pay_june = next(c for c in june.categories if c.id == pay_id)
    # Groceries shows the live overspend in June.
    assert g_june.available == -30_000
    # The payment category's available grew by the full 80k spent on the card
    # (money set aside / owed to the card).
    assert pay_june.available == 80_000
    assert pay_june.is_payment is True

    july = eng.get_state("2026-07-01")
    g_july = next(c for c in july.categories if c.id == groceries)
    # The 30k overspend floored (no negative carry) but did NOT dock RTA: it is
    # credit debt, not cash overspend.
    assert g_july.available == 0
    # RTA July = 200k income - 50k assigned - 0 cash overspend.
    assert july.ready_to_assign == 150_000


def test_mixed_cash_and_credit_overspend_only_cash_docks(db):
    """When a category overspends partly on cash and partly on credit, only the
    cash portion docks RTA."""
    chk = _checking(db)
    cc = _credit(db)
    _income(db, 200_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)

    eng.assign(groceries, 50_000, month="2026-06-01")
    # Spend 40k cash + 40k credit = 80k total, overspending the 50k by 30k.
    _spend(db, chk, groceries, "Groceries", -40_000, "2026-06-10", "g-cash")
    _spend(db, cc, groceries, "Groceries", -40_000, "2026-06-20", "g-credit")

    july = eng.get_state("2026-07-01")
    # Overspend is 30k. Credit spend magnitude is 40k, which caps the credit
    # part at min(30k, 40k) = 30k. So the entire overspend is credit -> 0 cash
    # dock. RTA July = 200k - 50k assigned.
    assert july.ready_to_assign == 150_000
