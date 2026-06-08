// ImportHistory — a table of past import batches, pulled from useImportHistory.
//
// Handles loading, error, and empty states. Columns: Imported at | Filename |
// Txns | Duplicates | Date range | (delete control). Each row can be deleted,
// which cascade-removes the transactions that came in from that upload. Delete
// is two-step: clicking "Delete" reveals an inline Confirm/Cancel so an upload
// (and its transactions) can't be removed by a single stray click.

import { useState } from 'react'

import { useDeleteImport, useImportHistory } from '../../lib/queries'
import type { ImportBatch } from '../../lib/types'

function dateRange(min: string | null, max: string | null): string {
  if (!min && !max) return '—'
  if (min && max) return min === max ? min : `${min} → ${max}`
  return (min ?? max) as string
}

export default function ImportHistory() {
  const { data, isLoading, isError } = useImportHistory()
  const deleteImport = useDeleteImport()
  // Which row is currently asking to confirm its deletion (batch id), if any.
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  const handleDelete = (id: number) => {
    deleteImport
      .mutateAsync(id)
      .then(() => {
        setConfirmingId(null)
      })
      .catch(() => {
        // Failure surfaces via deleteImport.isError below; keep the confirm
        // affordance open so the user can retry. Swallow the rejection so it
        // doesn't become an unhandled promise rejection.
      })
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-800">Import history</h2>

      {deleteImport.isError ? (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
        >
          Failed to delete the upload. Please try again.
        </div>
      ) : null}

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
              <th scope="col" className="px-3 py-2 text-right">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((batch: ImportBatch) => {
              const isConfirming = confirmingId === batch.id
              const isDeleting =
                deleteImport.isPending && deleteImport.variables === batch.id
              return (
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
                  <td className="px-3 py-2 text-right text-sm">
                    {isConfirming ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="text-xs text-slate-500">
                          Delete {batch.txn_count} txn
                          {batch.txn_count === 1 ? '' : 's'}?
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDelete(batch.id)}
                          disabled={isDeleting}
                          className="rounded-md bg-rose-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-300 disabled:opacity-60"
                        >
                          {isDeleting ? 'Deleting…' : 'Confirm'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmingId(null)}
                          disabled={isDeleting}
                          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60"
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmingId(batch.id)}
                        aria-label={`Delete ${batch.filename ?? 'upload'}`}
                        className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-rose-200"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
