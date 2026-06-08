// RuleList — auto-categorization rules in priority order, each with an
// "Apply now" (categorize existing matching transactions) and "Delete" action.

import type { Rule } from '../../lib/types'

interface RuleListProps {
  rules: Rule[]
  onApply: (id: number) => void
  onDelete: (id: number) => void
  /** Id of a rule with an in-flight apply/delete, to show a pending state. */
  busyId?: number | null
}

/** Human-readable condition, e.g. `payee contains "AMAZON"`. */
function describe(rule: Rule): string {
  const verb =
    rule.match_type === 'regex' ? 'matches regex' : rule.match_type
  return `${rule.match_field} ${verb} "${rule.pattern}"`
}

function categoryLabel(rule: Rule): string {
  const name = rule.category_name ?? rule.category_id
  return rule.group_name ? `${rule.group_name}: ${name}` : name
}

export default function RuleList({
  rules,
  onApply,
  onDelete,
  busyId,
}: RuleListProps) {
  // Defensive sort: lower priority runs first (backend already orders, but
  // don't rely on it for display).
  const sorted = [...rules].sort((a, b) => a.priority - b.priority)

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full" data-testid="rule-list">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
            <th className="px-3 py-2">Priority</th>
            <th className="px-3 py-2">Condition</th>
            <th className="px-3 py-2">Category</th>
            <th className="px-3 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((rule) => {
            const busy = busyId === rule.id
            return (
              <tr
                key={rule.id}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
              >
                <td className="px-3 py-2 text-sm tabular-nums text-slate-500">
                  {rule.priority}
                </td>
                <td className="px-3 py-2 text-sm text-slate-800">
                  {describe(rule)}
                </td>
                <td className="px-3 py-2 text-sm text-slate-700">
                  {categoryLabel(rule)}
                </td>
                <td className="px-3 py-2 text-right text-sm">
                  <button
                    type="button"
                    onClick={() => onApply(rule.id)}
                    disabled={busy}
                    aria-label={`Apply rule ${rule.id}`}
                    className="mr-2 rounded border border-emerald-300 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                  >
                    Apply now
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(rule.id)}
                    disabled={busy}
                    aria-label={`Delete rule ${rule.id}`}
                    className="rounded border border-rose-300 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
