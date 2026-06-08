// MetricCards — a responsive grid of headline numbers for the dashboard.
//
// Sources from useSettingsSummary (counts + ready_to_assign). Ready to Assign
// can also come from useBudget, but the summary carries the same value so we
// use it directly to keep the cards single-sourced. Uncategorized and active
// alert counts are highlighted (amber) when greater than zero.

import { useBudget, useSettingsSummary } from '../../lib/queries'
import { formatMoney } from '../../lib/money'

interface MetricCardProps {
  cardKey: string
  label: string
  value: string
  highlight?: boolean
}

function MetricCard({ cardKey, label, value, highlight }: MetricCardProps) {
  return (
    <div
      data-testid={`metric-${cardKey}`}
      className={
        'rounded-lg border bg-white p-4 ' +
        (highlight ? 'border-amber-300 bg-amber-50' : 'border-slate-200')
      }
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div
        className={
          'mt-1 text-2xl font-bold tabular-nums ' +
          (highlight ? 'text-amber-700' : 'text-slate-900')
        }
      >
        {value}
      </div>
    </div>
  )
}

export default function MetricCards() {
  const { data: summary, isLoading } = useSettingsSummary()
  // useBudget provides the authoritative RTA; fall back to the summary value.
  const { data: budget } = useBudget()

  if (isLoading || !summary) {
    return (
      <div
        data-testid="metric-cards-loading"
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6"
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-lg border border-slate-200 bg-slate-100"
          />
        ))}
      </div>
    )
  }

  const readyToAssign = budget?.ready_to_assign ?? summary.ready_to_assign

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
      <MetricCard
        cardKey="ready_to_assign"
        label="Ready to Assign"
        value={formatMoney(readyToAssign)}
      />
      <MetricCard
        cardKey="accounts"
        label="Accounts"
        value={String(summary.account_count)}
      />
      <MetricCard
        cardKey="categories"
        label="Categories"
        value={String(summary.category_count)}
      />
      <MetricCard
        cardKey="transactions"
        label="Transactions"
        value={String(summary.transaction_count)}
      />
      <MetricCard
        cardKey="uncategorized"
        label="Uncategorized"
        value={String(summary.uncategorized_count)}
        highlight={summary.uncategorized_count > 0}
      />
      <MetricCard
        cardKey="active_alerts"
        label="Active Alerts"
        value={String(summary.active_alert_count)}
        highlight={summary.active_alert_count > 0}
      />
    </div>
  )
}
