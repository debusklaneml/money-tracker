import { formatMoney } from '../../lib/money'
import { useBudget } from '../../lib/queries'
import type { BudgetState } from '../../lib/types'

interface ReadyToAssignHeaderProps {
  /** Budget month as `YYYY-MM-01`. Forwarded to `useBudget`. */
  month?: string
}

/**
 * Format a `YYYY-MM-01` month string as a friendly label, e.g. "June 2026".
 * Falls back to the raw input if it can't be parsed (no date library).
 */
function formatMonthLabel(month: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(month)
  if (!match) return month

  const year = Number(match[1])
  const monthIndex = Number(match[2]) - 1
  const MONTHS = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ]
  if (monthIndex < 0 || monthIndex > 11) return month
  return `${MONTHS[monthIndex]} ${year}`
}

type RtaState = 'to-assign' | 'all-assigned' | 'over-assigned'

interface StateTreatment {
  state: RtaState
  label: string
  /** Card surface / ring classes. */
  card: string
  /** Big RTA amount classes. */
  amount: string
  /** State label (eyebrow) classes. */
  eyebrow: string
}

function treatmentFor(rta: number): StateTreatment {
  if (rta > 0) {
    return {
      state: 'to-assign',
      label: 'Ready to Assign',
      card: 'bg-emerald-50 ring-emerald-200',
      amount: 'text-emerald-600',
      eyebrow: 'text-emerald-700',
    }
  }
  if (rta < 0) {
    return {
      state: 'over-assigned',
      label: 'Over-assigned',
      card: 'bg-rose-50 ring-rose-200',
      amount: 'text-rose-600',
      eyebrow: 'text-rose-700',
    }
  }
  return {
    state: 'all-assigned',
    label: 'All money assigned',
    card: 'bg-slate-50 ring-slate-200',
    amount: 'text-slate-700',
    eyebrow: 'text-slate-500',
  }
}

function SecondaryFigure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </span>
      <span className="text-sm font-semibold tabular-nums text-slate-700">
        {value}
      </span>
    </div>
  )
}

function HeaderSkeleton() {
  return (
    <section
      role="status"
      aria-busy="true"
      aria-label="Loading budget"
      className="animate-pulse rounded-2xl bg-slate-50 p-6 ring-1 ring-slate-200"
    >
      <div className="h-3 w-24 rounded bg-slate-200" />
      <div className="mt-3 h-10 w-48 rounded bg-slate-200" />
      <div className="mt-5 flex gap-8">
        <div className="h-8 w-28 rounded bg-slate-200" />
        <div className="h-8 w-28 rounded bg-slate-200" />
      </div>
    </section>
  )
}

function Loaded({ data }: { data: BudgetState }) {
  const treatment = treatmentFor(data.ready_to_assign)

  return (
    <section
      role="status"
      data-state={treatment.state}
      className={[
        'rounded-2xl p-6 ring-1 transition-colors',
        treatment.card,
      ].join(' ')}
    >
      <div className="flex flex-col gap-1">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
          {formatMonthLabel(data.month)}
        </p>
        <h2
          className={[
            'text-sm font-semibold uppercase tracking-wide',
            treatment.eyebrow,
          ].join(' ')}
        >
          {treatment.label}
        </h2>
        <p
          data-testid="rta-amount"
          className={[
            'text-4xl font-black tabular-nums leading-tight',
            treatment.amount,
          ].join(' ')}
        >
          {formatMoney(data.ready_to_assign)}
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-8 border-t border-slate-200/70 pt-4">
        <SecondaryFigure
          label="Income this month"
          value={formatMoney(data.income_month)}
        />
        <SecondaryFigure
          label="Assigned"
          value={formatMoney(data.assigned_total)}
        />
      </div>
    </section>
  )
}

export default function ReadyToAssignHeader({
  month,
}: ReadyToAssignHeaderProps) {
  const { data, isLoading, isError } = useBudget(month)

  if (isError) {
    return (
      <section
        role="status"
        className="rounded-2xl bg-rose-50 p-6 text-sm font-medium text-rose-700 ring-1 ring-rose-200"
      >
        Couldn&rsquo;t load the budget for this month.
      </section>
    )
  }

  if (isLoading || !data) {
    return <HeaderSkeleton />
  }

  return <Loaded data={data} />
}
