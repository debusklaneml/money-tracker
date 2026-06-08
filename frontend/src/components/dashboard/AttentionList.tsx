// AttentionList — things needing action, derived from the settings summary and
// active alerts.
//
// Items:
//   - uncategorized count (>0) → links to /transactions
//   - one item per active (non-dismissed) alert, top ~5, colored by severity
// If nothing needs attention, a friendly "All clear" state is shown.

import { Link } from 'react-router-dom'

import { useAlerts, useSettingsSummary } from '../../lib/queries'
import type { Alert } from '../../lib/types'

const MAX_ALERTS = 5

function severityClasses(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'border-rose-300 bg-rose-50 text-rose-700'
    case 'warning':
      return 'border-amber-300 bg-amber-50 text-amber-700'
    default:
      return 'border-sky-300 bg-sky-50 text-sky-700'
  }
}

export default function AttentionList() {
  const { data: summary } = useSettingsSummary()
  const { data: alerts } = useAlerts()

  const uncategorized = summary?.uncategorized_count ?? 0
  const activeAlerts: Alert[] = (alerts ?? [])
    .filter((a) => !a.dismissed)
    .slice(0, MAX_ALERTS)

  const hasUncategorized = uncategorized > 0
  const nothingToDo = !hasUncategorized && activeAlerts.length === 0

  return (
    <div
      data-testid="attention-list"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-700">Needs Attention</h2>

      {nothingToDo ? (
        <div className="mt-4 flex items-center gap-2 text-sm text-emerald-600">
          <span aria-hidden>✓</span>
          <span>All clear — nothing needs your attention.</span>
        </div>
      ) : (
        <ul className="mt-3 space-y-2">
          {hasUncategorized && (
            <li>
              <Link
                to="/transactions"
                className="flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 hover:bg-amber-100"
              >
                <span className="font-medium">
                  {uncategorized} uncategorized transaction
                  {uncategorized === 1 ? '' : 's'}
                </span>
                <span aria-hidden>→</span>
              </Link>
            </li>
          )}

          {activeAlerts.map((alert, index) => (
            <li
              key={alert.id ?? `alert-${index}`}
              className={
                'rounded-md border px-3 py-2 text-sm ' +
                severityClasses(alert.severity)
              }
            >
              <div className="font-medium">{alert.title}</div>
              {alert.description && (
                <div className="mt-0.5 text-xs opacity-80">
                  {alert.description}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
