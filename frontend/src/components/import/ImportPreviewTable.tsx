// ImportPreviewTable — non-committing preview of what an import WOULD add.
//
// Renders the parsed accounts (as chips), a summary line, an "already
// imported" warning banner, and a table of the new transactions. To stay
// responsive for huge files we cap the rendered rows and show a visible
// "+X more" note rather than silently truncating.

import { formatMoney } from '../../lib/money'
import type { ImportPreview } from '../../lib/types'

interface ImportPreviewTableProps {
  preview: ImportPreview
}

const MAX_ROWS = 100

function dateRange(min: string | null, max: string | null): string | null {
  if (!min && !max) return null
  if (min && max) return min === max ? min : `${min} → ${max}`
  return min ?? max
}

export default function ImportPreviewTable({
  preview,
}: ImportPreviewTableProps) {
  const txns = preview.new_transactions
  const shown = txns.slice(0, MAX_ROWS)
  const hidden = txns.length - shown.length
  const range = dateRange(preview.date_min, preview.date_max)

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-700">Accounts:</span>
        {preview.accounts.length === 0 ? (
          <span className="text-sm text-slate-500">None detected</span>
        ) : (
          preview.accounts.map((account) => (
            <span
              key={account}
              className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700"
            >
              {account}
            </span>
          ))
        )}
      </div>

      <p className="text-sm text-slate-600" data-testid="preview-summary">
        <span className="font-semibold text-slate-800">
          {txns.length} new
        </span>
        {', '}
        <span className="font-semibold text-slate-800">
          {preview.duplicate_count} duplicate
          {preview.duplicate_count === 1 ? '' : 's'}
        </span>
        {range ? <span className="text-slate-500"> · {range}</span> : null}
      </p>

      {preview.already_imported_file ? (
        <div
          role="alert"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800"
        >
          This file appears to have already been imported. Committing again may
          create duplicates.
        </div>
      ) : null}

      {txns.length === 0 ? (
        <p className="text-sm text-slate-500">
          No new transactions to import from this file.
        </p>
      ) : (
        <div>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
                <th scope="col" className="px-3 py-2 text-left">
                  Date
                </th>
                <th scope="col" className="px-3 py-2 text-left">
                  Payee
                </th>
                <th scope="col" className="px-3 py-2 text-left">
                  Memo
                </th>
                <th scope="col" className="px-3 py-2 text-right">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((txn) => {
                const negative = txn.amount < 0
                return (
                  <tr
                    key={txn.id}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
                  >
                    <td className="px-3 py-2 text-sm tabular-nums text-slate-600">
                      {txn.date}
                    </td>
                    <td className="px-3 py-2 text-sm text-slate-800">
                      {txn.payee_name ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-sm text-slate-500">
                      {txn.memo ?? ''}
                    </td>
                    <td
                      data-negative={negative}
                      className={
                        'px-3 py-2 text-right text-sm font-medium tabular-nums ' +
                        (negative ? 'text-rose-600' : 'text-emerald-600')
                      }
                    >
                      {formatMoney(txn.amount)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {hidden > 0 ? (
            <p className="px-3 py-2 text-xs text-slate-500" data-testid="row-cap-note">
              Showing first {MAX_ROWS} of {txns.length} transactions · +{hidden}{' '}
              more not shown
            </p>
          ) : null}
        </div>
      )}
    </div>
  )
}
