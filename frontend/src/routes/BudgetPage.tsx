import { useState } from 'react'
import ReadyToAssignHeader from '../components/budget/ReadyToAssignHeader'
import EnvelopeGrid from '../components/budget/EnvelopeGrid'
import MoveMoneyPanel from '../components/budget/MoveMoneyPanel'

/**
 * The budget cockpit: the Ready-to-Assign header over the editable envelope
 * grid, plus a Move-money panel for covering overspending. All three read the
 * current month's budget from the same `useBudget` query, so an assignment or
 * move refreshes the header and grid automatically.
 */
export default function BudgetPage() {
  const [moveOpen, setMoveOpen] = useState(false)

  return (
    <section className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-900">Budget</h1>
        <button
          type="button"
          onClick={() => setMoveOpen(true)}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400"
        >
          Move money
        </button>
      </div>
      <ReadyToAssignHeader />
      <EnvelopeGrid />
      <MoveMoneyPanel open={moveOpen} onClose={() => setMoveOpen(false)} />
    </section>
  )
}
