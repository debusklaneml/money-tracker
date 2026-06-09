import { useState } from 'react'
import ReadyToAssignHeader from '../components/budget/ReadyToAssignHeader'
import EnvelopeGrid from '../components/budget/EnvelopeGrid'
import MoveMoneyPanel from '../components/budget/MoveMoneyPanel'
import AutoAssignBar from '../components/budget/AutoAssignBar'

/** First-of-month string (YYYY-MM-01) for the current calendar month. */
function currentMonth(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}-01`
}

/** Shift a YYYY-MM-01 month string by `delta` months, staying first-of-month. */
export function shiftMonth(month: string, delta: number): string {
  const match = /^(\d{4})-(\d{2})/.exec(month)
  if (!match) return month
  const year = Number(match[1])
  const monthIndex = Number(match[2]) - 1 + delta
  const date = new Date(year, monthIndex, 1)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}-01`
}

/**
 * The budget cockpit: a month switcher over the Ready-to-Assign header, the
 * editable envelope grid, and a Move-money panel for covering overspending.
 *
 * The month switcher lets you assign money into FUTURE months (YNAB: assigning
 * ahead removes that money from the current month's Ready to Assign; the
 * furthest funded month shows the true remaining RTA). All children read the
 * same `useBudget(month)` query, so an assignment or move refreshes them all.
 */
export default function BudgetPage() {
  const [moveOpen, setMoveOpen] = useState(false)
  const [month, setMonth] = useState<string>(currentMonth)
  const isFuture = month > currentMonth()
  const isPast = month < currentMonth()

  return (
    <section className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-slate-900">Budget</h1>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => setMonth((m) => shiftMonth(m, -1))}
              className="rounded-lg border border-slate-200 px-2 py-1 text-sm font-semibold text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-400"
            >
              ‹
            </button>
            <button
              type="button"
              onClick={() => setMonth(currentMonth())}
              disabled={!isFuture && month === currentMonth()}
              className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:opacity-40"
            >
              Today
            </button>
            <button
              type="button"
              aria-label="Next month"
              onClick={() => setMonth((m) => shiftMonth(m, 1))}
              className="rounded-lg border border-slate-200 px-2 py-1 text-sm font-semibold text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-400"
            >
              ›
            </button>
          </div>
          {isFuture && (
            <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">
              Future month
            </span>
          )}
          {isPast && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
              Past month
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setMoveOpen(true)}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400"
        >
          Move money
        </button>
      </div>
      <ReadyToAssignHeader month={month} />
      <AutoAssignBar month={month} />
      <EnvelopeGrid month={month} />
      <MoveMoneyPanel
        open={moveOpen}
        onClose={() => setMoveOpen(false)}
        month={month}
      />
    </section>
  )
}
