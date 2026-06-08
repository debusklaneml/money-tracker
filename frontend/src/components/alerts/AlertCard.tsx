// AlertCard — a single detected alert with severity styling and per-card
// acknowledge/dismiss actions. Presentational: all data + callbacks are passed
// in; the page owns the mutations and busy state.

import type { Alert } from '../../lib/types'

interface AlertCardProps {
  alert: Alert
  onAcknowledge: (id: number) => void
  onDismiss: (id: number) => void
  /** Disable this card's actions while one of its mutations is in flight. */
  busy?: boolean
}

/** Tailwind classes for the severity badge, keyed by severity string. */
const severityBadge: Record<string, string> = {
  critical: 'border-rose-200 bg-rose-50 text-rose-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
}

/** Left accent border colour keyed by severity. */
const severityAccent: Record<string, string> = {
  critical: 'border-l-rose-400',
  warning: 'border-l-amber-400',
  info: 'border-l-blue-400',
}

/**
 * Format an ISO timestamp as a short, readable local date+time, e.g.
 * "Jun 7, 2026, 3:04 PM". Returns an empty string for missing/invalid input —
 * no date library, just Intl via toLocaleString.
 */
function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function AlertCard({
  alert,
  onAcknowledge,
  onDismiss,
  busy,
}: AlertCardProps) {
  const badge = severityBadge[alert.severity] ?? severityBadge.info
  const accent = severityAccent[alert.severity] ?? severityAccent.info
  const acknowledged = alert.acknowledged_at != null
  const created = formatDate(alert.created_at)

  return (
    <article
      data-testid={`alert-card-${alert.id}`}
      className={
        'rounded-lg border border-l-4 border-slate-200 bg-white p-4 ' + accent
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={
                'rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ' +
                badge
              }
            >
              {alert.severity}
            </span>
            <h3 className="truncate text-sm font-semibold text-slate-900">
              {alert.title}
            </h3>
            {acknowledged && (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                Acknowledged
              </span>
            )}
          </div>
          {alert.description && (
            <p className="mt-1 text-sm text-slate-600">{alert.description}</p>
          )}
          {created && (
            <p className="mt-1 text-xs text-slate-400">{created}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {!acknowledged && (
            <button
              type="button"
              onClick={() => {
                if (alert.id != null) onAcknowledge(alert.id)
              }}
              disabled={busy || alert.id == null}
              aria-label={`Acknowledge alert ${alert.id}`}
              className="rounded border border-emerald-300 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
            >
              Acknowledge
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              if (alert.id != null) onDismiss(alert.id)
            }}
            disabled={busy || alert.id == null}
            aria-label={`Dismiss alert ${alert.id}`}
            className="rounded border border-rose-300 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
          >
            Dismiss
          </button>
        </div>
      </div>
    </article>
  )
}
