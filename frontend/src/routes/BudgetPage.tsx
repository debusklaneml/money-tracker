import ReadyToAssignHeader from '../components/budget/ReadyToAssignHeader'
import EnvelopeGrid from '../components/budget/EnvelopeGrid'

/**
 * The budget cockpit: the Ready-to-Assign header over the editable envelope
 * grid. Both read the current month's budget from the same `useBudget` query,
 * so an assignment made in the grid refreshes the header automatically.
 */
export default function BudgetPage() {
  return (
    <section className="p-6 space-y-6">
      <ReadyToAssignHeader />
      <EnvelopeGrid />
    </section>
  )
}
