// ImportPage — the OFX/QFX import flow.
//
// Flow:
//   1. Pick a file (Dropzone) → kick off a non-committing preview.
//   2. Show ImportPreviewTable with what WOULD be imported.
//   3. "Commit import" actually writes the transactions, then we show a
//      success summary and clear the pending file.
//   4. ImportHistory renders below at all times.
//
// All data lives in the spine hooks; this component only holds the selected
// File and orchestrates the preview → commit transition.

import { useState } from 'react'

import Dropzone from '../components/import/Dropzone'
import ImportPreviewTable from '../components/import/ImportPreviewTable'
import ImportHistory from '../components/import/ImportHistory'
import { useCommitImport, usePreviewImport } from '../lib/queries'

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Something went wrong. Please try again.'
}

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null)

  const preview = usePreviewImport()
  const commit = useCommitImport()

  const handleFile = (selected: File) => {
    setFile(selected)
    // Drop any prior commit result/error from a previous file.
    commit.reset()
    preview.mutate(selected)
  }

  const handleCommit = () => {
    if (!file) return
    commit.mutateAsync(file).then(() => {
      // Success: clear the pending file & preview; the success summary lives
      // on commit.data and survives this reset.
      setFile(null)
      preview.reset()
    })
  }

  const handleReset = () => {
    setFile(null)
    preview.reset()
    commit.reset()
  }

  const result = commit.data

  return (
    <section className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Import</h1>

      {/* Success summary from the most recent commit. */}
      {result ? (
        <div
          role="status"
          className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-4"
        >
          <p className="text-sm font-semibold text-emerald-800">
            Imported {result.filename}
          </p>
          <p className="text-sm text-emerald-700">
            {result.imported} imported · {result.duplicates} duplicate
            {result.duplicates === 1 ? '' : 's'} · {result.auto_categorized}{' '}
            auto-categorized
          </p>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-200"
          >
            Import another file
          </button>
        </div>
      ) : null}

      {/* Dropzone — hidden once a file is selected and being previewed. */}
      {!file && !result ? (
        <Dropzone onFile={handleFile} disabled={preview.isPending} />
      ) : null}

      {/* Preview pending state. */}
      {preview.isPending ? (
        <div
          role="status"
          className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500"
        >
          Analyzing {file?.name ?? 'file'}…
        </div>
      ) : null}

      {/* Preview error. */}
      {preview.isError ? (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
        >
          Could not preview this file: {errorMessage(preview.error)}
        </div>
      ) : null}

      {/* Preview + commit affordances. */}
      {preview.data && !preview.isPending ? (
        <div className="space-y-4">
          <ImportPreviewTable preview={preview.data} />

          {commit.isError ? (
            <div
              role="alert"
              className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
            >
              Import failed: {errorMessage(commit.error)}
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleCommit}
              disabled={commit.isPending}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:opacity-60"
            >
              {commit.isPending ? 'Importing…' : 'Commit import'}
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={commit.isPending}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60"
            >
              Choose another
            </button>
          </div>
        </div>
      ) : null}

      <ImportHistory />
    </section>
  )
}
