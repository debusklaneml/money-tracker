"""The budgeting engine — the dollar-job math we now own (no YNAB).

Model (all amounts in milliunits, inflows positive / outflows negative):

* Income      = uncategorized inflows. Money enters the budget here.
* Assigning   = moving money from Ready-to-Assign into a category for a month.
* Activity    = the signed sum of a category's categorized transactions.
* Available   = Σ(assigned + activity) for a category over all months to date,
                so unspent money rolls forward into the next month.
* Ready to Assign = Σ(all income) − Σ(all assigned), cumulative to the month.
                Spending does NOT reduce RTA; it reduces a category's Available.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.cache.database import Database, LOCAL_BUDGET_ID


def current_month() -> str:
    """Current budget month as YYYY-MM-01."""
    return datetime.now().strftime("%Y-%m-01")


@dataclass
class CategoryState:
    id: str
    group: str
    name: str
    assigned: int     # assigned this month
    activity: int     # activity this month (negative = spending)
    available: int    # rolling balance through this month


@dataclass
class BudgetState:
    month: str
    ready_to_assign: int
    income_month: int
    income_total: int
    assigned_total: int
    categories: list[CategoryState]

    @property
    def overspent(self) -> list[CategoryState]:
        return [c for c in self.categories if c.available < 0]


class BudgetEngine:
    """Computes the budget state and applies assignments to the local DB."""

    def __init__(self, db: Database, budget_id: str = LOCAL_BUDGET_ID):
        self.db = db
        self.budget_id = budget_id

    # --- writes -------------------------------------------------------
    def assign(self, category_id: str, amount: int, month: Optional[str] = None) -> None:
        """Set a category's assigned amount for a month (the core write)."""
        month = month or current_month()
        # budgeted is the source of truth; activity/available are computed live.
        self.db.upsert_monthly_budget(self.budget_id, month, category_id, amount, 0, 0)

    def move(self, from_id: str, to_id: str, amount: int, month: Optional[str] = None) -> None:
        """Move money between two envelopes by adjusting their assignments."""
        month = month or current_month()
        assigned = self.db.assigned_in_month(self.budget_id, month)
        self.assign(from_id, assigned.get(from_id, 0) - amount, month)
        self.assign(to_id, assigned.get(to_id, 0) + amount, month)

    # --- reads --------------------------------------------------------
    def get_state(self, month: Optional[str] = None) -> BudgetState:
        month = month or current_month()
        bid = self.budget_id

        assigned_cum = self.db.assigned_by_category(bid, month)
        activity_cum = self.db.activity_by_category(bid, month)
        assigned_now = self.db.assigned_in_month(bid, month)
        activity_now = self.db.activity_in_month(bid, month)

        categories = []
        for c in self.db.get_categories(bid, include_hidden=False):
            cid = c["id"]
            categories.append(CategoryState(
                id=cid,
                group=c["category_group_name"] or "",
                name=c["name"],
                assigned=assigned_now.get(cid, 0),
                activity=activity_now.get(cid, 0),
                available=assigned_cum.get(cid, 0) + activity_cum.get(cid, 0),
            ))

        income_total = self.db.income_total(bid, month)
        assigned_total = self.db.total_assigned(bid, month)
        return BudgetState(
            month=month,
            ready_to_assign=income_total - assigned_total,
            income_month=self.db.income_in_month(bid, month),
            income_total=income_total,
            assigned_total=assigned_total,
            categories=categories,
        )
