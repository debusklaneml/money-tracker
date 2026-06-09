"""Targets: underfunded / needed-this-month math (bud-bjl).

Covers monthly, yearly (spread + anchored sinking fund) and custom every-N
cadences in both ``full`` and ``refill`` modes, at the pure-function level and
through the engine's BudgetState.
"""

import tempfile
from pathlib import Path

import pytest

from src.cache.database import Database, LOCAL_BUDGET_ID
from src.budget.engine import BudgetEngine
from src.budget.targets import Target, monthly_need, underfunded


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


# --- pure function tests --------------------------------------------------
def test_monthly_full_need_is_full_amount():
    t = Target(amount=100_000, cadence="monthly", mode="full")
    assert monthly_need(t, "2026-06-01") == 100_000
    # full mode: underfunded ignores carry-in, only subtracts what's assigned.
    assert underfunded(t, "2026-06-01", assigned=0, available_carryin=999_000) == 100_000
    assert underfunded(t, "2026-06-01", assigned=40_000, available_carryin=0) == 60_000


def test_monthly_refill_uses_carryin():
    t = Target(amount=100_000, cadence="monthly", mode="refill")
    # leftover available reduces the need
    assert underfunded(t, "2026-06-01", assigned=0, available_carryin=30_000) == 70_000
    assert underfunded(t, "2026-06-01", assigned=0, available_carryin=100_000) == 0
    assert underfunded(t, "2026-06-01", assigned=20_000, available_carryin=30_000) == 50_000


def test_yearly_spread_is_one_twelfth():
    t = Target(amount=120_000, cadence="yearly", mode="refill")
    assert monthly_need(t, "2026-06-01") == 10_000


def test_yearly_anchored_sinking_fund():
    # Whole amount due in December, nothing the other months.
    t = Target(amount=120_000, cadence="yearly", mode="refill", month_of_year=12)
    assert monthly_need(t, "2026-06-01") == 0
    assert monthly_need(t, "2026-12-01") == 120_000


def test_custom_every_three_months():
    t = Target(amount=90_000, cadence="custom", mode="refill", every_n_months=3)
    assert monthly_need(t, "2026-06-01") == 30_000


def test_weekly_spread():
    # $10/week -> ~$43.33/month (52/12 weeks).
    t = Target(amount=10_000, cadence="weekly", mode="refill")
    assert monthly_need(t, "2026-06-01") == 10_000 * 52 // 12


# --- engine integration ---------------------------------------------------
def test_engine_surfaces_underfunded_monthly(db):
    _income(db, 500_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    db.upsert_category_target(LOCAL_BUDGET_ID, groceries, 100_000,
                              cadence="monthly", mode="refill")
    eng = BudgetEngine(db)

    state = eng.get_state("2026-06-01")
    g = next(c for c in state.categories if c.id == groceries)
    assert g.target_amount == 100_000
    assert g.target_needed == 100_000
    assert g.underfunded == 100_000  # nothing assigned yet

    eng.assign(groceries, 40_000, month="2026-06-01")
    g = next(c for c in eng.get_state("2026-06-01").categories if c.id == groceries)
    assert g.underfunded == 60_000  # 100k target - 40k assigned


def test_engine_refill_target_accounts_for_carryin(db):
    """A refill target's underfunded shrinks by the balance carried into the
    month from a prior month's assignment."""
    _income(db, 500_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    db.upsert_category_target(LOCAL_BUDGET_ID, groceries, 100_000,
                              cadence="monthly", mode="refill")
    eng = BudgetEngine(db)
    # Fund 100k in June, spend nothing -> 100k carries into July.
    eng.assign(groceries, 100_000, month="2026-06-01")

    july = eng.get_state("2026-07-01")
    g = next(c for c in july.categories if c.id == groceries)
    # Refill: already has 100k cushion carried in, so July needs nothing.
    assert g.underfunded == 0


def test_engine_full_target_ignores_carryin(db):
    """A full-repeat target always wants the whole amount each month."""
    _income(db, 500_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    db.upsert_category_target(LOCAL_BUDGET_ID, groceries, 100_000,
                              cadence="monthly", mode="full")
    eng = BudgetEngine(db)
    eng.assign(groceries, 100_000, month="2026-06-01")

    july = eng.get_state("2026-07-01")
    g = next(c for c in july.categories if c.id == groceries)
    # Full: still wants 100k in July even though 100k carried in.
    assert g.underfunded == 100_000


def test_deleting_target_clears_it_from_budget_state(db):
    """Once a target is deleted, the engine stops reporting target/underfunded."""
    _income(db, 500_000, "2026-06-01")
    groceries = _cat(db, "Groceries")
    db.upsert_category_target(LOCAL_BUDGET_ID, groceries, 100_000,
                              cadence="monthly", mode="refill")
    eng = BudgetEngine(db)
    g = next(c for c in eng.get_state("2026-06-01").categories if c.id == groceries)
    assert g.target_amount == 100_000 and g.underfunded == 100_000

    db.delete_category_target(groceries)
    g = next(c for c in eng.get_state("2026-06-01").categories if c.id == groceries)
    assert g.target_amount is None
    assert g.target_needed == 0
    assert g.underfunded == 0
