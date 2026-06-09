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
* ``yearly``  — 1/12 of the target per month (spread evenly), or the full amount
                in the anchor month if ``month_of_year`` matches (sinking fund).
* ``custom``  — every N months; 1/N of the target per month.

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
    month_of_year: Optional[int] = None

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


def monthly_need(target: Target, month: str) -> int:
    """The amount this target wants set aside *during* ``month`` (milliunits).

    This is cadence-only — it ignores what is already there. ``refill`` mode
    still wants to reach the same per-cycle contribution, but the underfunded
    helper subtracts the existing balance.
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
            # Sinking fund: the whole amount is due in the anchor month, nothing
            # the rest of the year (it accumulates via available carry-in).
            return amt if _month_int(month) == target.month_of_year else 0
        # Spread evenly across the year.
        return amt // 12
    if cadence == "custom":
        n = max(1, target.every_n_months)
        return amt // n
    return amt


def underfunded(target: Target, month: str, assigned: int, available_carryin: int) -> int:
    """Milliunits still missing for ``month`` to satisfy the target.

    ``assigned`` is what is already assigned to the category THIS month.
    ``available_carryin`` is the category's available balance carried in from the
    prior month (floored at 0 by the engine), i.e. what is already sitting in the
    envelope before this month's assignment.

    * full mode:   need = monthly_need; underfunded = max(0, need − assigned).
    * refill mode: target the *available* balance to reach ``monthly_need`` worth
                   of cushion. underfunded = max(0, need − carryin − assigned).
    """
    need = monthly_need(target, month)
    if need <= 0:
        return 0
    if target.mode == "full":
        return max(0, need - assigned)
    # refill: leftover available reduces the need.
    return max(0, need - available_carryin - assigned)
