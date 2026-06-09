"""The budgeting engine — the dollar-job math we now own (no YNAB).

Model (all amounts in milliunits, inflows positive / outflows negative)
=======================================================================

* **Income**    = uncategorized inflows. Money enters the budget here, and
                  ONLY once it actually exists in an on-budget account — you
                  cannot assign income that has not arrived.
* **Assigning** = moving money out of Ready-to-Assign into a category for a
                  given month. Assigning into a *future* month is allowed and
                  removes that money from the current month's Ready to Assign.
* **Activity**  = the signed sum of a category's categorized transactions.
* **Available** = the category's rolling envelope balance through a month.

YNAB cash-overspend rollover
----------------------------
Category balances roll forward month to month — we do NOT reset to zero. But a
category that ends a month with a *negative* Available because of **cash
overspending** does NOT carry that negative into the next month. Instead the
overspend is "absorbed" at the month boundary (the category floors at 0 going
in to the next month) and the same shortfall is deducted from the next month's
Ready to Assign. So overspending always has to be covered with real dollars,
just on the following month's books.

Concretely, per category ``c`` we use the recurrence::

    available(c, M) = max(0, available(c, M-1)) + assigned(c, M) + activity(c, M)

The ``max(0, …)`` floors only the *carry-in* from the prior month; the current
month's Available can still go negative (so live overspending shows red). The
amount floored away at the end of a prior month is the "cash overspend" that
docks a later month's Ready to Assign.

Ready to Assign
---------------
::

    RTA(M) = Σ income through M
           − Σ assigned across ALL months (the whole cash pool)
           − Σ prior-month cash overspends absorbed at boundaries before M

Income is gated by month (you can only assign money that has *arrived* by M),
but assignments draw from one shared pool of cash, so the assigned term sums
*every* month — past and future. That is what makes assigning into a future
month immediately lower the current month's RTA, and it makes the furthest
month that has any money assigned report the most accurate remaining RTA (it
has the most income recognised while subtracting the same global assignments).
Spending itself does NOT reduce RTA (it reduces a category's Available); only
the *rolled-over* overspend at a month boundary does.

Cash vs. credit
---------------
Only **cash** overspending docks Ready to Assign. Credit-card overspending is
handled differently (it increases card debt, covered later via a credit-card
payment category) and is out of scope here (tracked as bud-px9). The
:meth:`BudgetEngine._overspend_is_cash` helper is the single seam where that
distinction will plug in; for now every account is treated as cash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.cache.database import Database, LOCAL_BUDGET_ID


def current_month() -> str:
    """Current budget month as YYYY-MM-01."""
    return datetime.now().strftime("%Y-%m-01")


class RTAExceededError(Exception):
    """Raised when an assignment would push Ready to Assign below zero.

    You cannot assign money that does not exist. ``available`` is how many
    milliunits *could* still be assigned to the category for the month (the
    current RTA plus whatever is already assigned to that category this month);
    ``requested`` is what the caller tried to set. The budget router translates
    this into an HTTP 400.
    """

    def __init__(self, requested: int, available: int):
        self.requested = requested
        self.available = available
        super().__init__(
            f"Cannot assign {requested}: only {available} is available to assign."
        )


@dataclass
class CategoryState:
    id: str
    group: str
    name: str
    assigned: int     # assigned this month
    activity: int     # activity this month (negative = spending)
    available: int    # rolling balance through this month (carry-in floored at 0)


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
        """Set a category's assigned amount for ``month`` (the core write).

        Guards Ready to Assign: the new assignment may not push RTA below zero
        (you cannot budget money that does not exist). ``amount`` is the new
        absolute assignment for the month, so the change to RTA is the *delta*
        against whatever is already assigned to this category that month.
        Raises :class:`RTAExceededError` when the delta exceeds the current RTA.
        """
        month = month or current_month()
        state = self.get_state(month)
        prior = self.db.assigned_in_month(self.budget_id, month).get(category_id, 0)
        delta = amount - prior
        if delta > state.ready_to_assign:
            # Most you may set this category to == its current assignment + RTA.
            max_assignable = prior + state.ready_to_assign
            raise RTAExceededError(requested=amount, available=max_assignable)
        # budgeted is the source of truth; activity/available are computed live.
        self.db.upsert_monthly_budget(self.budget_id, month, category_id, amount, 0, 0)

    def move(self, from_id: str, to_id: str, amount: int, month: Optional[str] = None) -> None:
        """Move money between two envelopes by adjusting their assignments.

        A move is RTA-neutral (one category's assignment goes down by exactly
        what another's goes up), so it must never trip the RTA guard. We write
        the raw assignments directly rather than going through :meth:`assign`.
        """
        month = month or current_month()
        assigned = self.db.assigned_in_month(self.budget_id, month)
        self.db.upsert_monthly_budget(
            self.budget_id, month, from_id, assigned.get(from_id, 0) - amount, 0, 0
        )
        self.db.upsert_monthly_budget(
            self.budget_id, month, to_id, assigned.get(to_id, 0) + amount, 0, 0
        )

    # --- overspend classification (cash vs credit) --------------------
    def _overspend_is_cash(self, category_id: str) -> bool:
        """Whether overspending in this category should dock Ready to Assign.

        Cash overspending rolls to next month's RTA; credit overspending does
        not (it becomes card debt, covered via a credit-card payment category —
        out of scope, bud-px9). Today every account is treated as cash, so this
        always returns True; it exists as the seam where the credit/cash split
        will later plug in.
        """
        return True

    # --- reads --------------------------------------------------------
    def _months_with_data(self, through_month: str) -> list[str]:
        """Distinct budget months that have assignments or activity, ≤ through_month.

        Sorted ascending. ``through_month`` is always included so the requested
        month is computed even if nothing has touched it yet.
        """
        months = self.db.active_months(self.budget_id, through_month)
        if through_month not in months:
            months.append(through_month)
        return sorted(months)

    def get_state(self, month: Optional[str] = None) -> BudgetState:
        month = month or current_month()
        bid = self.budget_id

        assigned_now = self.db.assigned_in_month(bid, month)
        activity_now = self.db.activity_in_month(bid, month)

        # Walk every month up to and including the requested one, applying the
        # YNAB carry-in floor per category and accumulating the cash overspend
        # absorbed at each *prior* month boundary (which docks this month's RTA).
        months = self._months_with_data(month)
        available: dict[str, int] = {}        # category -> rolling available
        prior_cash_overspend = 0              # absorbed at boundaries before `month`
        for m in months:
            assigned_m = self.db.assigned_in_month(bid, m)
            activity_m = self.db.activity_in_month(bid, m)
            if m == month:
                # Current month: floor only the carry-in; current overspend is
                # allowed to show negative.
                touched = set(available) | set(assigned_m) | set(activity_m)
                for cid in touched:
                    available[cid] = (
                        max(0, available.get(cid, 0))
                        + assigned_m.get(cid, 0)
                        + activity_m.get(cid, 0)
                    )
                break
            # A fully-elapsed prior month: roll forward, and absorb any cash
            # overspend (negative end-of-month available) into the RTA dock.
            touched = set(available) | set(assigned_m) | set(activity_m)
            for cid in touched:
                end = (
                    max(0, available.get(cid, 0))
                    + assigned_m.get(cid, 0)
                    + activity_m.get(cid, 0)
                )
                if end < 0 and self._overspend_is_cash(cid):
                    prior_cash_overspend += -end
                    available[cid] = 0
                else:
                    available[cid] = end

        categories = []
        for c in self.db.get_categories(bid, include_hidden=False):
            cid = c["id"]
            categories.append(CategoryState(
                id=cid,
                group=c["category_group_name"] or "",
                name=c["name"],
                assigned=assigned_now.get(cid, 0),
                activity=activity_now.get(cid, 0),
                available=available.get(cid, 0),
            ))

        income_total = self.db.income_total(bid, month)
        # RTA draws from one pool of cash, so EVERY assignment (including ones
        # made into future months) reduces it — global sum, not month <= cap.
        assigned_total = self.db.total_assigned_all_months(bid)
        ready_to_assign = income_total - assigned_total - prior_cash_overspend
        return BudgetState(
            month=month,
            ready_to_assign=ready_to_assign,
            income_month=self.db.income_in_month(bid, month),
            income_total=income_total,
            assigned_total=assigned_total,
            categories=categories,
        )
