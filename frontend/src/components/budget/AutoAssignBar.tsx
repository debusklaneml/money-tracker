// AutoAssignBar — one-click auto-fill of a month's assignments by strategy.
//
// Strategies map to the backend /budget/auto-assign endpoint. Every strategy
// respects the Ready-to-Assign guard server-side, so the UI just fires the
// mutation and lets the budget query refresh.

import { useState } from 'react'

import { useAutoAssign } from '../../lib/queries'
import { formatMoney } from '../../lib/money'
import type { AutoAssignStrategy } from '../../lib/types'

interface AutoAssignBarProps {
  month?: string
}

const STRATEGIES: { value: AutoAssignStrategy; label: string }[] = [
  { value: 'underfunded', label: 'Fill to target (underfunded)' },
  { value: 'assigned_last_month', label: 'Assigned last month' },
  { value: 'average_assigned', label: 'Average assigned (3 mo)' },
  { value: 'average_spent', label: 'Average spent (3 mo)' },
]

export default function AutoAssignBar({ month }: AutoAssignBarProps) {
  const [strategy, setStrategy] = useState<AutoAssignStrategy>('underfunded')
  const autoAssign = useAutoAssign()

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
      <span className="text-sm font-semibold text-slate-700">Auto-assign</span>
      <select
        aria-label="Auto-assign strategy"
        value={strategy}
        onChange={(e) => setStrategy(e.target.value as AutoAssignStrategy)}
        className="rounded-lg border border-slate-200 px-2 py-1 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-400"
      >
        {STRATEGIES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() =>
          autoAssign.mutate({ strategy, month: month ?? null })
        }
        disabled={autoAssign.isPending}
        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:opacity-60"
      >
        {autoAssign.isPending ? 'Assigning…' : 'Apply'}
      </button>
      {autoAssign.isError && (
        <span role="alert" className="text-xs text-rose-600">
          {autoAssign.error instanceof Error
            ? autoAssign.error.message
            : 'Auto-assign failed.'}
        </span>
      )}
      {autoAssign.isSuccess && (
        <span role="status" className="text-xs font-medium text-emerald-600">
          {autoAssign.data
            ? `Assigned — ${formatMoney(autoAssign.data.ready_to_assign)} remaining to assign`
            : 'Assigned.'}
        </span>
      )}
    </div>
  )
}
