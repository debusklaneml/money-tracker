// EnvelopeGrid — the editable budget table at the heart of the budget cockpit.
//
// Columns: Category | Assigned (editable) | Activity | Available.
// Categories are grouped by their `group` field, with a group header row
// (plus an Assigned subtotal) preceding each group's category rows. Editing
// the Assigned cell commits an assignment through the API via useAssign().

import { useMemo, useRef, useState } from 'react'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type Row,
} from '@tanstack/react-table'

import { useAssign, useBudget } from '../../lib/queries'
import { formatMoney, parseMoneyInput, toInputString } from '../../lib/money'
import type { CategoryState } from '../../lib/types'

interface EnvelopeGridProps {
  month?: string
}

const columnHelper = createColumnHelper<CategoryState>()

/**
 * Editable Assigned cell.
 *
 * Displays the assigned value via formatMoney. Clicking/focusing turns it into
 * a controlled <input> seeded with the current display value. On blur or Enter
 * the text is parsed with parseMoneyInput; if it is valid AND changed we fire
 * the assign mutation, otherwise we revert. Escape cancels the edit.
 */
function AssignedCell({
  category,
  month,
}: {
  category: CategoryState
  month?: string
}) {
  const assign = useAssign()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  // Guards against a single edit session being finalized twice: pressing Enter
  // (or Escape) sets editing=false, which unmounts the input and fires its
  // onBlur — without this flag that trailing blur would re-run commit.
  const finishedRef = useRef(false)

  // Seed the input with a plain numeric display (no "$"), e.g. "100.00".
  const startEditing = () => {
    finishedRef.current = false
    setDraft(toInputString(category.assigned))
    setEditing(true)
  }

  // Finalize the edit session exactly once. `apply` distinguishes commit
  // (Enter/blur) from cancel (Escape).
  const finish = (apply: boolean) => {
    if (finishedRef.current) return
    finishedRef.current = true
    if (apply) {
      const parsed = parseMoneyInput(draft)
      // Invalid input → revert silently, no API call.
      // Unchanged value → no API call.
      if (parsed !== null && parsed !== category.assigned) {
        assign.mutate({
          category_id: category.id,
          amount: parsed,
          month: month ?? null,
        })
      }
    }
    setEditing(false)
    setDraft('')
  }

  const commit = () => finish(true)
  const cancel = () => finish(false)

  if (editing) {
    return (
      <input
        autoFocus
        type="text"
        inputMode="decimal"
        aria-label={`Assigned for ${category.name}`}
        className="w-28 rounded border border-emerald-400 bg-white px-2 py-1 text-right text-sm text-slate-900 outline-none ring-2 ring-emerald-200"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            commit()
          } else if (e.key === 'Escape') {
            e.preventDefault()
            cancel()
          }
        }}
      />
    )
  }

  return (
    <button
      type="button"
      aria-label={`Assigned for ${category.name}`}
      onClick={startEditing}
      disabled={assign.isPending}
      className="w-28 rounded px-2 py-1 text-right text-sm tabular-nums text-slate-800 hover:bg-emerald-50 focus:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-200 disabled:opacity-60"
    >
      {formatMoney(category.assigned)}
    </button>
  )
}

export default function EnvelopeGrid({ month }: EnvelopeGridProps) {
  const { data, isLoading, isError } = useBudget(month)

  const categories = useMemo<CategoryState[]>(
    () => data?.categories ?? [],
    [data],
  )

  // Column definitions. The Assigned column renders the editable cell; the
  // others format milliunits and style negatives.
  const columns = useMemo(
    () => [
      columnHelper.accessor('name', {
        header: 'Category',
        cell: (info) => (
          <span className="text-sm text-slate-800">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('assigned', {
        header: 'Assigned',
        cell: (info) => (
          <AssignedCell category={info.row.original} month={month} />
        ),
      }),
      columnHelper.accessor('activity', {
        header: 'Activity',
        cell: (info) => (
          <span className="text-sm tabular-nums text-slate-500">
            {formatMoney(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor('available', {
        header: 'Available',
        cell: (info) => {
          const value = info.getValue()
          const negative = value < 0
          return (
            <span
              data-negative={negative}
              className={
                'text-sm font-medium tabular-nums ' +
                (negative ? 'text-rose-600' : 'text-emerald-600')
              }
            >
              {formatMoney(value)}
            </span>
          )
        },
      }),
    ],
    [month],
  )

  const table = useReactTable({
    data: categories,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  // Pre-group rows in memory, preserving first-seen group order. This keeps the
  // grouping logic explicit and well-typed while still using react-table for
  // the row model / cell rendering.
  const rows = table.getRowModel().rows
  const groups = useMemo(() => {
    const order: string[] = []
    const byGroup = new Map<string, Row<CategoryState>[]>()
    for (const row of rows) {
      const key = row.original.group
      let bucket = byGroup.get(key)
      if (!bucket) {
        bucket = []
        byGroup.set(key, bucket)
        order.push(key)
      }
      bucket.push(row)
    }
    return order.map((name) => ({ name, rows: byGroup.get(name)! }))
  }, [rows])

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
        Loading budget…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        Failed to load budget. Please try again.
      </div>
    )
  }

  if (categories.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No categories yet. Create a category to start budgeting.
      </div>
    )
  }

  const headerGroups = table.getHeaderGroups()
  const columnCount = columns.length

  return (
    <table
      data-testid="envelope-grid"
      className="w-full border-collapse text-left"
    >
      <thead>
        {headerGroups.map((headerGroup) => (
          <tr
            key={headerGroup.id}
            className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400"
          >
            {headerGroup.headers.map((header, idx) => (
              <th
                key={header.id}
                scope="col"
                className={
                  'px-3 py-2 ' + (idx === 0 ? 'text-left' : 'text-right')
                }
              >
                {header.isPlaceholder
                  ? null
                  : flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
              </th>
            ))}
          </tr>
        ))}
      </thead>

      {groups.map((group) => {
        const subtotal = group.rows.reduce(
          (sum, row) => sum + row.original.assigned,
          0,
        )
        return (
          <tbody key={group.name}>
            <tr className="bg-slate-50">
              <th
                scope="colgroup"
                colSpan={columnCount - 1}
                className="px-3 py-2 text-left text-sm font-semibold text-slate-700"
              >
                {group.name}
              </th>
              <td className="px-3 py-2 text-right text-sm font-semibold tabular-nums text-slate-500">
                {formatMoney(subtotal)}
              </td>
            </tr>

            {group.rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
              >
                {row.getVisibleCells().map((cell, idx) => (
                  <td
                    key={cell.id}
                    className={
                      'px-3 py-2 align-middle ' +
                      (idx === 0 ? 'text-left' : 'text-right')
                    }
                  >
                    {flexRender(
                      cell.column.columnDef.cell,
                      cell.getContext(),
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        )
      })}
    </table>
  )
}
