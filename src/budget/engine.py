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
handled differently: it increases card debt, covered later via the card's
credit-card payment category. :meth:`BudgetEngine.get_state` splits a prior
month's overspend into its credit part (capped by that month's credit spend on
the category — becomes debt, no RTA dock) and its cash part (docks RTA), using
:meth:`_payment_activity` to set the money aside into each card's payment
category.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.cache.database import Database, LOCAL_BUDGET_ID
from src.budget.targets import Target, monthly_need, underfunded


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
    # Target info (None when the category has no funding target).
    target_amount: Optional[int] = None      # milliunits
    target_cadence: Optional[str] = None     # weekly | monthly | yearly | custom
    target_mode: Optional[str] = None        # full | refill
    target_needed: int = 0                   # what this month wants (cadence only)
    underfunded: int = 0                     # still missing after assigned/carry-in
    is_payment: bool = False                 # credit-card payment category?


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

    # --- auto-assign (bud-6hv) ----------------------------------------
    @staticmethod
    def _prev_month(month: str, back: int = 1) -> str:
        """The month string ``back`` months before ``month`` (YYYY-MM-01)."""
        y, m = int(month[:4]), int(month[5:7])
        idx = (y * 12 + (m - 1)) - back
        return f"{idx // 12:04d}-{idx % 12 + 1:02d}-01"

    def auto_assign_amounts(self, month: str, strategy: str,
                            lookback: int = 3) -> dict[str, int]:
        """Compute a per-category TARGET assignment for ``month`` by strategy.

        Returns ``{category_id: desired_total_assigned_for_month}``. The caller
        (or :meth:`auto_assign`) is responsible for applying these through the
        RTA guard. Strategies:

        * ``underfunded``        — fill each category to its target's needed
                                   amount this month (uses bud-bjl targets).
        * ``assigned_last_month``— repeat last month's assignment.
        * ``average_assigned``   — trailing ``lookback``-month average of
                                   assignments.
        * ``average_spent``      — trailing ``lookback``-month average of spend
                                   magnitude (outflows).

        Only categories with a positive desired amount are returned. The desired
        amount is the ABSOLUTE assignment for the month (not a delta).
        """
        bid = self.budget_id
        result: dict[str, int] = {}

        if strategy == "underfunded":
            state = self.get_state(month)
            for c in state.categories:
                # underfunded already nets out what's assigned this month, so the
                # desired absolute assignment is current assigned + underfunded.
                if c.underfunded > 0:
                    result[c.id] = c.assigned + c.underfunded
            return result

        if strategy == "assigned_last_month":
            prev = self._prev_month(month, 1)
            for cid, amt in self.db.assigned_in_month(bid, prev).items():
                if amt > 0:
                    result[cid] = amt
            return result

        if strategy in ("average_assigned", "average_spent"):
            n = max(1, lookback)
            totals: dict[str, int] = {}
            for k in range(1, n + 1):
                m = self._prev_month(month, k)
                if strategy == "average_assigned":
                    data = self.db.assigned_in_month(bid, m)
                    for cid, amt in data.items():
                        totals[cid] = totals.get(cid, 0) + amt
                else:  # average_spent: spend magnitude (negative activity -> positive)
                    data = self.db.activity_in_month(bid, m)
                    for cid, amt in data.items():
                        if amt < 0:
                            totals[cid] = totals.get(cid, 0) + (-amt)
            for cid, total in totals.items():
                avg = total // n
                if avg > 0:
                    result[cid] = avg
            return result

        raise ValueError(f"Unknown auto-assign strategy: {strategy!r}")

    def auto_assign(self, month: str, strategy: str,
                    lookback: int = 3) -> dict[str, int]:
        """Apply :meth:`auto_assign_amounts`, respecting the RTA guard.

        Iterates categories by descending desired delta and assigns as much as
        possible. When Ready to Assign runs out, remaining categories that would
        increase their assignment are partially funded (up to the remaining RTA)
        or skipped. Lowering an existing assignment is never done — auto-assign
        only adds money. Returns ``{category_id: amount_actually_assigned}`` for
        the categories it changed.
        """
        desired = self.auto_assign_amounts(month, strategy, lookback)
        applied: dict[str, int] = {}
        assigned_now = self.db.assigned_in_month(self.budget_id, month)
        # RTA is one cash pool and we only ever ADD money into `month`, so each
        # assign() reduces Ready to Assign by exactly the granted delta. Track it
        # locally and seed once, rather than recomputing the (expensive,
        # multi-month) get_state on every funded category. assign()'s own RTA
        # guard still backstops correctness.
        rta = self.get_state(month).ready_to_assign
        # Sort by largest increase first so the biggest needs get funded.
        for cid, target in sorted(
            desired.items(),
            key=lambda kv: kv[1] - assigned_now.get(kv[0], 0),
            reverse=True,
        ):
            if rta <= 0:
                break
            current = assigned_now.get(cid, 0)
            if target <= current:
                continue  # never lower an assignment
            delta = target - current
            grant = min(delta, rta)
            new_amount = current + grant
            self.assign(cid, new_amount, month)
            applied[cid] = new_amount
            rta -= grant
        return applied

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

    def _payment_activity(self, month: str, pay_by_account: dict[str, str]) -> dict[str, int]:
        """Synthetic inflow for each credit-card payment category in ``month``.

        When you spend on a credit card, that purchase's money (already budgeted
        in the spending category) is owed to the card; YNAB moves it into the
        card's *payment* category so it is set aside to pay the bill. We model
        this as a positive activity on the payment category equal to the
        magnitude of categorized spending on that card. (Inflows/refunds on the
        card net it back down.)

        ``pay_by_account`` is the precomputed ``{account_id: payment_category_id}``
        map (fetched once per get_state, not per month) to avoid an N+1 lookup.
        Returns ``{payment_category_id: +credit_spend_magnitude}``. Empty when
        there are no credit accounts / payment categories.
        """
        by_account = self.db.credit_activity_in_month(self.budget_id, month)  # acct -> net
        if not by_account:
            return {}
        result: dict[str, int] = {}
        for acct_id, net in by_account.items():
            pay_id = pay_by_account.get(acct_id)
            if pay_id is None:
                continue
            # net is negative for spending; the payment need grows by -net.
            result[pay_id] = result.get(pay_id, 0) - net
        return result

    def get_state(self, month: Optional[str] = None) -> BudgetState:
        month = month or current_month()
        bid = self.budget_id

        assigned_now = self.db.assigned_in_month(bid, month)
        activity_now = self.db.activity_in_month(bid, month)

        # Categories whose spending lands on a credit card route into card debt
        # rather than cash overspend; payment categories are funded with cash.
        # The account -> payment-category map is static across months, so fetch
        # it once here rather than per-month inside the walk below.
        pay_by_account = self.db.payment_categories_by_account(bid)
        has_credit = bool(pay_by_account)

        # Walk every month up to and including the requested one, applying the
        # YNAB carry-in floor per category and accumulating the cash overspend
        # absorbed at each *prior* month boundary (which docks this month's RTA).
        months = self._months_with_data(month)
        available: dict[str, int] = {}        # category -> rolling available
        prior_cash_overspend = 0              # absorbed at boundaries before `month`
        payment_now: dict[str, int] = {}      # payment-cat synthetic activity (this month)
        for m in months:
            assigned_m = self.db.assigned_in_month(bid, m)
            activity_m = dict(self.db.activity_in_month(bid, m))
            # Per-category portion of this month's spend that hit a credit card
            # (negative). This part of any overspend becomes debt, not an RTA dock.
            credit_m = (
                self.db.credit_activity_by_category_in_month(bid, m)
                if has_credit else {}
            )
            # Fold credit spending into each card's payment category as a
            # positive inflow (money set aside to pay the card).
            pay_m = self._payment_activity(m, pay_by_account) if has_credit else {}
            for pid, amt in pay_m.items():
                activity_m[pid] = activity_m.get(pid, 0) + amt
            if m == month:
                payment_now = pay_m
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
                if end < 0:
                    overspend = -end
                    # Split overspend into the credit part (became debt — does
                    # NOT dock RTA) and the cash part (docks RTA). credit_m[cid]
                    # is negative for spending; its magnitude caps the
                    # credit-absorbed amount. Clamp into [0, overspend]: when
                    # card refunds exceed card spend credit_m[cid] is POSITIVE,
                    # and without the max(0, …) credit_part would go negative and
                    # inflate cash_part past the real overspend — silently
                    # destroying budgetable Ready to Assign.
                    credit_part = max(0, min(overspend, -credit_m.get(cid, 0)))
                    cash_part = overspend - credit_part
                    if cash_part > 0:
                        prior_cash_overspend += cash_part
                    available[cid] = 0
                else:
                    available[cid] = end

        # Targets, keyed by category id.
        targets = self.db.get_category_targets(bid)
        # Carry-in available per category (floored at 0) is what was rolling
        # before this month's assignment landed; needed for refill targets. For
        # payment categories `available` was built from activity WITH the
        # synthetic payment inflow folded in (payment_now), so subtract that too
        # — otherwise this month's set-aside leaks into the supposed pre-month
        # carry-in and under-reports a refill target's need.
        carryin = {cid: max(0, available.get(cid, 0) - assigned_now.get(cid, 0)
                            - activity_now.get(cid, 0) - payment_now.get(cid, 0))
                   for cid in available}

        categories = []
        for c in self.db.get_categories(bid, include_hidden=False):
            cid = c["id"]
            is_payment = c["payment_account_id"] is not None
            cs = CategoryState(
                id=cid,
                group=c["category_group_name"] or "",
                name=c["name"],
                assigned=assigned_now.get(cid, 0),
                # Payment categories surface the card's spend as their activity.
                activity=activity_now.get(cid, 0) + (
                    payment_now.get(cid, 0) if is_payment else 0
                ),
                available=available.get(cid, 0),
                is_payment=is_payment,
            )
            t_row = targets.get(cid)
            if t_row is not None:
                target = Target.from_row(t_row)
                cs.target_amount = target.amount
                cs.target_cadence = target.cadence
                cs.target_mode = target.mode
                cs.target_needed = monthly_need(target, month)
                cs.underfunded = underfunded(
                    target, month,
                    assigned=cs.assigned,
                    available_carryin=carryin.get(cid, 0),
                )
            categories.append(cs)

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
