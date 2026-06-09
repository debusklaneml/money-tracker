"""Auto-assign strategies (bud-6hv)."""

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


def _clear_seeded_targets(db):
    """Remove the default seeded targets so a test controls the target set."""
    for cid in list(db.get_category_targets(LOCAL_BUDGET_ID)):
        db.delete_category_target(cid)


def _income(db, amount, month, txn_id="inc"):
    db.upsert_transaction(
        txn_id=txn_id, budget_id=LOCAL_BUDGET_ID, account_id=None, account_name=None,
        txn_date=month, amount=amount, memo=None, cleared="cleared", approved=True,
        flag_color=None, payee_id=None, payee_name="PAYROLL", category_id=None,
        category_name=None, transfer_account_id=None, transfer_transaction_id=None,
        import_id=None, deleted=False,
    )


def _spend(db, cat_id, cat_name, amount, txn_date, txn_id):
    db.upsert_transaction(
        txn_id=txn_id, budget_id=LOCAL_BUDGET_ID, account_id=None, account_name=None,
        txn_date=txn_date, amount=amount, memo=None, cleared="cleared", approved=True,
        flag_color=None, payee_id=None, payee_name="STORE", category_id=cat_id,
        category_name=cat_name, transfer_account_id=None, transfer_transaction_id=None,
        import_id=None, deleted=False,
    )


def test_prev_month_helper():
    assert BudgetEngine._prev_month("2026-06-01", 1) == "2026-05-01"
    assert BudgetEngine._prev_month("2026-01-01", 1) == "2025-12-01"
    assert BudgetEngine._prev_month("2026-03-01", 3) == "2025-12-01"


def test_auto_assign_underfunded_fills_to_target(db):
    _clear_seeded_targets(db)
    _income(db, 500_000, "2026-06-01")
    groceries, gas = _cat(db, "Groceries"), _cat(db, "Gas / Fuel")
    db.upsert_category_target(LOCAL_BUDGET_ID, groceries, 100_000,
                              cadence="monthly", mode="refill")
    db.upsert_category_target(LOCAL_BUDGET_ID, gas, 40_000,
                              cadence="monthly", mode="refill")
    eng = BudgetEngine(db)

    applied = eng.auto_assign("2026-06-01", "underfunded")
    assert applied[groceries] == 100_000
    assert applied[gas] == 40_000

    state = eng.get_state("2026-06-01")
    assert next(c for c in state.categories if c.id == groceries).assigned == 100_000
    assert next(c for c in state.categories if c.id == gas).assigned == 40_000


def test_auto_assign_underfunded_respects_rta_guard(db):
    """When cash runs out, the biggest need is funded first and the rest is
    partially funded / skipped — never exceeding RTA."""
    _clear_seeded_targets(db)
    _income(db, 120_000, "2026-06-01")
    groceries, gas = _cat(db, "Groceries"), _cat(db, "Gas / Fuel")
    db.upsert_category_target(LOCAL_BUDGET_ID, groceries, 100_000,
                              cadence="monthly", mode="refill")
    db.upsert_category_target(LOCAL_BUDGET_ID, gas, 40_000,
                              cadence="monthly", mode="refill")
    eng = BudgetEngine(db)

    eng.auto_assign("2026-06-01", "underfunded")
    state = eng.get_state("2026-06-01")
    # Only 120k available: groceries (bigger need) fully funded, gas gets the
    # remaining 20k.
    assert next(c for c in state.categories if c.id == groceries).assigned == 100_000
    assert next(c for c in state.categories if c.id == gas).assigned == 20_000
    assert state.ready_to_assign == 0


def test_auto_assign_assigned_last_month(db):
    # Income lands in May so the May assignments are valid (income exists).
    _income(db, 500_000, "2026-05-01")
    groceries, gas = _cat(db, "Groceries"), _cat(db, "Gas / Fuel")
    eng = BudgetEngine(db)
    # May assignments.
    eng.assign(groceries, 80_000, month="2026-05-01")
    eng.assign(gas, 30_000, month="2026-05-01")

    applied = eng.auto_assign("2026-06-01", "assigned_last_month")
    assert applied[groceries] == 80_000
    assert applied[gas] == 30_000


def test_auto_assign_average_spent(db):
    _income(db, 900_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    eng = BudgetEngine(db)
    # Spend 60k, 90k, 30k over the prior 3 months -> avg 60k.
    _spend(db, groceries, "Groceries", -60_000, "2026-03-15", "s1")
    _spend(db, groceries, "Groceries", -90_000, "2026-04-15", "s2")
    _spend(db, groceries, "Groceries", -30_000, "2026-05-15", "s3")

    amounts = eng.auto_assign_amounts("2026-06-01", "average_spent", lookback=3)
    assert amounts[groceries] == 60_000


def test_auto_assign_unknown_strategy_raises(db):
    eng = BudgetEngine(db)
    with pytest.raises(ValueError):
        eng.auto_assign("2026-06-01", "nonsense")
