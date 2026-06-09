"""Category funding targets and "underfunded" math.

A target says how much a category should hold/receive on a cadence. All amounts
are milliunits. Two modes:

* ``full``   — set aside the FULL target amount every cycle (balances
               accumulate). Needed-this-month for a monthly full target is the
               whole amount, regardless of what is already available.
* ``refill`` — top up the category's *available* balance to the target each
               cycle ("have a balance of X"). Needed = max(0, target − available
               carried in), so leftover available reduces next cycle's need.

Cadence determines the per-month share of the target:

* ``weekly``  — the target is per week; a month needs ~4.33 weeks of it. We use
                the exact number of weeks that *start* in the month is messy, so
                we approximate a month as (52/12) weeks for the monthly need.
* ``monthly`` — the target applies every month.
* ``yearly``  — without a due month, 1/12 of the target per month (spread
                evenly). With ``month_of_year`` set, it is a *by-date* sinking
                fund: the remaining amount is spread smoothly across the months
                between now and the due month (YNAB "by date" rule).
* ``custom``  — every N months. Without a due anchor, 1/N of the target per
                month. With ``month_of_year`` set, the remaining amount is
                spread across the months until that due month, wrapping by N.

YNAB "true expense" / "by date" rule
------------------------------------
Irregular costs are broken into smaller periodic funding amounts BEFORE the
bill arrives::

    need-this-month = ceil((target − available_toward_target) / months_until_due)

``months_until_due`` counts from the viewed month up to and including the due
month (so a bill due *this* month has ``months_until_due == 1`` and needs the
full remaining amount). If the due month has already passed in the current
cycle, it rolls forward to the next occurrence (the modular arithmetic does
this for free). Once ``available`` already covers the target, the need is 0.

The "needed this month" is the amount that SHOULD be assigned in the given
month to stay on track. "underfunded" is what is still missing after accounting
for what is already assigned (full mode) or already available (refill mode).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# A month is ~52/12 weeks. Keep integer milliunits by computing on the raw
# amount and using integer division at the end.
_WEEKS_PER_MONTH_NUM = 52
_WEEKS_PER_MONTH_DEN = 12


@dataclass(frozen=True)
class Target:
    amount: int                 # milliunits
    cadence: str = "monthly"    # weekly | monthly | yearly | custom
    mode: str = "refill"        # full | refill
    every_n_months: int = 1     # for custom
    day_of_month: Optional[int] = None
    month_of_year: Optional[int] = None  # due-month anchor (1-12)

    @classmethod
    def from_row(cls, row) -> "Target":
        return cls(
            amount=int(row["amount_milliunits"]),
            cadence=row["cadence"] or "monthly",
            mode=row["mode"] or "refill",
            every_n_months=int(row["every_n_months"] or 1),
            day_of_month=row["day_of_month"],
            month_of_year=row["month_of_year"],
        )


def _month_int(month: str) -> int:
    """Calendar month number (1-12) from a YYYY-MM-01 string."""
    return int(month[5:7])


def _months_until_due(current_month: int, due_month: int, cycle: int) -> int:
    """Months from ``current_month`` up to and including the next ``due_month``.

    Both months are 1-based. ``cycle`` is the length of the funding cycle in
    months (12 for yearly, N for custom every-N). Returns a value in
    ``1..cycle``: the same month as the due month yields 1 (fund it all now);
    a due month that already passed this cycle wraps to the next occurrence.
    """
    cycle = max(1, cycle)
    # Distance forward (0..cycle-1) to the due month, then +1 so "this month"
    # means "due now → fund the full remaining this month".
    delta = (due_month - current_month) % cycle
    return delta + 1


def _by_date_need(target: Target, month: str, available_carryin: int, cycle: int) -> int:
    """By-date spread: remaining amount / months until the due month.

    ``remaining`` is what is still missing to reach the target given what is
    already sitting in the envelope (``available_carryin``). The result is the
    amount to set aside *this* month so the envelope reaches the target by the
    due month, spread as evenly as possible. Rounds UP so integer division
    never leaves the goal short in the final month.
    """
    remaining = target.amount - max(0, available_carryin)
    if remaining <= 0:
        return 0
    months = _months_until_due(_month_int(month), target.month_of_year, cycle)
    if months <= 1:
        return remaining
    # Ceiling division to avoid perpetually under-funding by rounding down.
    return (remaining + months - 1) // months


def monthly_need(
    target: Target,
    month: str,
    available_carryin: Optional[int] = None,
) -> int:
    """The amount this target wants set aside *during* ``month`` (milliunits).

    For cadences without a due-month anchor this is cadence-only: it ignores
    what is already there and ``refill`` mode relies on :func:`underfunded` to
    subtract the existing balance.

    For *by-date* targets (yearly or custom with ``month_of_year`` set) and a
    supplied ``available_carryin``, this returns the YNAB by-date contribution:
    ``remaining / months_until_due``, which already accounts for the balance
    already accumulated. When ``available_carryin`` is ``None`` (e.g. callers
    that only want the cadence figure) the by-date target falls back to its
    even per-cycle share so existing display logic still gets a sensible number.
    """
    amt = target.amount
    cadence = target.cadence
    if cadence == "monthly":
        return amt
    if cadence == "weekly":
        # Per-week amount spread across an average month.
        return amt * _WEEKS_PER_MONTH_NUM // _WEEKS_PER_MONTH_DEN
    if cadence == "yearly":
        if target.month_of_year:
            if available_carryin is None:
                # No balance context: fall back to an even per-cycle share.
                return amt // 12
            return _by_date_need(target, month, available_carryin, cycle=12)
        # Spread evenly across the year.
        return amt // 12
    if cadence == "custom":
        n = max(1, target.every_n_months)
        if target.month_of_year:
            if available_carryin is None:
                return amt // n
            return _by_date_need(target, month, available_carryin, cycle=n)
        return amt // n
    return amt


def _is_by_date(target: Target) -> bool:
    """True when the target funds toward a specific due month (by-date spread)."""
    return target.month_of_year is not None and target.cadence in ("yearly", "custom")


def underfunded(target: Target, month: str, assigned: int, available_carryin: int) -> int:
    """Milliunits still missing for ``month`` to satisfy the target.

    ``assigned`` is what is already assigned to the category THIS month.
    ``available_carryin`` is the category's available balance carried in from the
    prior month (floored at 0 by the engine), i.e. what is already sitting in the
    envelope before this month's assignment.

    * by-date (yearly/custom with a due month): need already nets out the
      carried-in balance (remaining / months_until_due), so underfunded only
      subtracts what is assigned this month.
    * full mode:   need = monthly_need; underfunded = max(0, need − assigned).
    * refill mode: target the *available* balance to reach ``monthly_need`` worth
                   of cushion. underfunded = max(0, need − carryin − assigned).
    """
    if _is_by_date(target):
        need = monthly_need(target, month, available_carryin=available_carryin)
        return max(0, need - assigned)
    need = monthly_need(target, month)
    if need <= 0:
        return 0
    if target.mode == "full":
        return max(0, need - assigned)
    # refill: leftover available reduces the need.
    return max(0, need - available_carryin - assigned)
