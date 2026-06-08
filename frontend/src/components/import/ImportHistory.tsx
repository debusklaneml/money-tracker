// ImportHistory — a table of past import batches, pulled from useImportHistory.
//
// Handles loading, error, and empty states. Columns: Imported at | Filename |
// Txns | Duplicates | Date range.

import { useImportHistory } from '../../lib/queries'
import type { ImportBatch } from '../../lib/types'

function dateRange(min: string | null, max: string | null): string {
  if (!min && !max) return '—'
  if (min && max) return min === max ? min : `${min} → ${max}`
  return (min ?? max) as string
}

export default function ImportHistory() {
  const { data, isLoading, isError } = useImportHistory()

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-800">Import history</h2>

      {isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading import history…
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          Failed to load import history.
        </div>
      ) : !data || data.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No imports yet.
        </div>
      ) : (
        <table
          data-testid="import-history"
          className="w-full border-collapse text-left"
        >
          <thead>
            <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <th scope="col" className="px-3 py-2 text-left">
                Imported at
              </th>
              <th scope="col" className="px-3 py-2 text-left">
                Filename
              </th>
              <th scope="col" className="px-3 py-2 text-right">
                Txns
              </th>
              <th scope="col" className="px-3 py-2 text-right">
                Duplicates
              </th>
              <th scope="col" className="px-3 py-2 text-left">
                Date range
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((batch: ImportBatch) => (
              <tr
                key={batch.id}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
              >
                <td className="px-3 py-2 text-sm tabular-nums text-slate-600">
                  {batch.imported_at ?? '—'}
                </td>
                <td className="px-3 py-2 text-sm text-slate-800">
                  {batch.filename ?? '—'}
                </td>
                <td className="px-3 py-2 text-right text-sm tabular-nums text-slate-700">
                  {batch.txn_count}
                </td>
                <td className="px-3 py-2 text-right text-sm tabular-nums text-slate-500">
                  {batch.duplicate_count}
                </td>
                <td className="px-3 py-2 text-sm text-slate-500">
                  {dateRange(batch.date_min, batch.date_max)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
