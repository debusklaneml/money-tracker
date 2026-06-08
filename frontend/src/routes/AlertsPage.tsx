// AlertsPage — list detected budget alerts with severity styling, run the
// detectors on demand (surfacing how many new alerts were found), and
// acknowledge or dismiss individual alerts. Data + mutations come from the
// spine hooks in lib/queries.

import { useMemo, useState } from 'react'

import AlertCard from '../components/alerts/AlertCard'
import {
  useAcknowledgeAlert,
  useAlerts,
  useDismissAlert,
  useRunAlerts,
} from '../lib/queries'
import type { Alert } from '../lib/types'

/** Sort weight: critical first, then warning, then info, then anything else. */
const severityRank: Record<string, number> = {
  critical: 0,
  warning: 1,
  info: 2,
}

function rank(severity: string): number {
  return severityRank[severity] ?? 3
}

export default function AlertsPage() {
  const { data: alerts, isLoading, isError } = useAlerts()
  const runAlerts = useRunAlerts()
  const dismissAlert = useDismissAlert()
  const acknowledgeAlert = useAcknowledgeAlert()

  // A single feedback channel for run/acknowledge/dismiss outcomes.
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)

  const errorText = (err: unknown, fallback: string) =>
    (err instanceof Error && err.message) || fallback

  const handleRun = () => {
    setFeedback(null)
    runAlerts.mutate(undefined, {
      onSuccess: (res) =>
        setFeedback({
          type: 'success',
          text: res.message ?? 'Detection complete.',
        }),
      onError: (err) =>
        setFeedback({
          type: 'error',
          text: errorText(err, 'Failed to run detection.'),
        }),
    })
  }

  const handleAcknowledge = (id: number) => {
    setFeedback(null)
    acknowledgeAlert.mutate(id, {
      onError: (err) =>
        setFeedback({
          type: 'error',
          text: errorText(err, 'Failed to acknowledge alert.'),
        }),
    })
  }

  const handleDismiss = (id: number) => {
    setFeedback(null)
    dismissAlert.mutate(id, {
      onError: (err) =>
        setFeedback({
          type: 'error',
          text: errorText(err, 'Failed to dismiss alert.'),
        }),
    })
  }

  const list = useMemo<Alert[]>(() => alerts ?? [], [alerts])

  // Sorted view: critical first, then by newest created_at within a severity.
  const sorted = useMemo(() => {
    return [...list].sort((a, b) => {
      const byRank = rank(a.severity) - rank(b.severity)
      if (byRank !== 0) return byRank
      const at = a.created_at ?? ''
      const bt = b.created_at ?? ''
      // Newest first: larger ISO string sorts earlier.
      return bt.localeCompare(at)
    })
  }, [list])

  // Severity counts for the summary line.
  const counts = useMemo(() => {
    const c = { critical: 0, warning: 0, info: 0 }
    for (const a of list) {
      if (a.severity === 'critical') c.critical += 1
      else if (a.severity === 'warning') c.warning += 1
      else if (a.severity === 'info') c.info += 1
    }
    return c
  }, [list])

  const summary = useMemo(() => {
    const parts: string[] = []
    if (counts.critical) parts.push(`${counts.critical} critical`)
    if (counts.warning) parts.push(`${counts.warning} warning`)
    if (counts.info) parts.push(`${counts.info} info`)
    return parts.join(' · ')
  }, [counts])

  // A single in-flight acknowledge/dismiss drives the per-card busy state.
  const busyId: number | null = acknowledgeAlert.isPending
    ? (acknowledgeAlert.variables ?? null)
    : dismissAlert.isPending
      ? (dismissAlert.variables ?? null)
      : null

  return (
    <section className="p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Alerts</h1>
          <p className="mt-1 text-sm text-slate-500">
            Detected budget warnings. Run detection to check for new issues.
          </p>
          {summary && (
            <p className="mt-1 text-sm font-medium text-slate-600">{summary}</p>
          )}
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={runAlerts.isPending}
          className="shrink-0 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          {runAlerts.isPending ? 'Running…' : 'Run detection'}
        </button>
      </div>

      {feedback && (
        <div
          role={feedback.type === 'error' ? 'alert' : 'status'}
          className={
            'rounded-lg border px-4 py-2 text-sm ' +
            (feedback.type === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800')
          }
        >
          {feedback.text}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading alerts…
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          Failed to load alerts. Please try again.
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No active alerts. Run detection to check.
        </div>
      ) : (
        <div className="space-y-3" data-testid="alert-list">
          {sorted.map((alert) => (
            <AlertCard
              key={alert.id ?? `${alert.alert_type}-${alert.title}`}
              alert={alert}
              onAcknowledge={handleAcknowledge}
              onDismiss={handleDismiss}
              busy={alert.id != null && busyId === alert.id}
            />
          ))}
        </div>
      )}
    </section>
  )
}
