// EnvelopeGrid — the editable budget table at the heart of the budget cockpit.
//
// Columns: Category | Assigned (editable) | Activity | Available.
// Categories are grouped by their `group` field, with a group header row
// (plus an Assigned subtotal) preceding each group's category rows. Editing
// the Assigned cell commits an assignment through the API via useAssign().

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type Row,
} from '@tanstack/react-table'

import {
  useAssign,
  useBudget,
  useDeleteCategoryTarget,
  useSetCategoryTarget,
} from '../../lib/queries'
import {
  formatMoney,
  fromDisplay,
  parseMoneyInput,
  toInputString,
} from '../../lib/money'
import type { CategoryState, TargetRequest } from '../../lib/types'

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

  // The backend rejects an assignment that would push Ready to Assign below
  // zero (you can't assign money you don't have) with a 400. Surface that
  // inline so the user sees why the edit didn't stick.
  return (
    <div className="flex flex-col items-end gap-0.5">
      <button
        type="button"
        aria-label={`Assigned for ${category.name}`}
        onClick={startEditing}
        disabled={assign.isPending}
        className="w-28 rounded px-2 py-1 text-right text-sm tabular-nums text-slate-800 hover:bg-emerald-50 focus:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-200 disabled:opacity-60"
      >
        {formatMoney(category.assigned)}
      </button>
      {assign.isError && (
        <span role="alert" className="max-w-[12rem] text-right text-xs text-rose-600">
          {assign.error instanceof Error
            ? assign.error.message
            : "Can't assign more than Ready to Assign."}
        </span>
      )}
    </div>
  )
}

type Cadence = 'weekly' | 'monthly' | 'yearly' | 'custom'
type Mode = 'full' | 'refill'

const CADENCES: { value: Cadence; label: string }[] = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'custom', label: 'Custom (every N months)' },
]

const MODES: { value: Mode; label: string }[] = [
  { value: 'full', label: 'Set aside the full amount' },
  { value: 'refill', label: 'Refill up to amount' },
]

const MONTHS: { value: number; label: string }[] = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
]

/**
 * Compact inline editor (popover) for a category's funding target. Lets the
 * user set an amount (dollars → milliunits), a cadence, a mode, and — for the
 * `custom` cadence — an every-N-months interval, persisting via
 * useSetCategoryTarget. For `yearly` and `custom` cadences the user can also
 * pick a *due month*: BUD then funds the remaining amount evenly across the
 * months leading up to it (YNAB "by date" spread) instead of dumping it all at
 * once. A "Clear target" action removes it via useDeleteCategoryTarget.
 * Dismissable with Escape or the Cancel button.
 */
function TargetEditor({
  category,
  onClose,
}: {
  category: CategoryState
  onClose: () => void
}) {
  const setTarget = useSetCategoryTarget()
  const deleteTarget = useDeleteCategoryTarget()

  const [amount, setAmount] = useState(
    category.target_amount != null ? toInputString(category.target_amount) : '',
  )
  const [cadence, setCadence] = useState<Cadence>(
    (category.target_cadence as Cadence | null) ?? 'monthly',
  )
  const [mode, setMode] = useState<Mode>(
    (category.target_mode as Mode | null) ?? 'refill',
  )
  const [everyN, setEveryN] = useState(
    category.target_every_n_months != null
      ? String(category.target_every_n_months)
      : '1',
  )
  // '' means "no due month / spread evenly". Otherwise a month number 1-12.
  const [dueMonth, setDueMonth] = useState(
    category.target_month_of_year != null
      ? String(category.target_month_of_year)
      : '',
  )
  const [error, setError] = useState<string | null>(null)

  const showDueMonth = cadence === 'yearly' || cadence === 'custom'

  const containerRef = useRef<HTMLDivElement>(null)

  // Move focus into the editor and dismiss on Escape.
  useEffect(() => {
    containerRef.current
      ?.querySelector<HTMLElement>('input, select, button')
      ?.focus()
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const handleSave = () => {
    const dollars = Number(amount.replace(/[$,\s]/g, ''))
    if (!Number.isFinite(dollars) || amount.trim() === '') {
      setError('Enter a valid amount.')
      return
    }
    const body: TargetRequest = {
      amount_milliunits: fromDisplay(dollars),
      cadence,
      mode,
    }
    if (cadence === 'custom') {
      const n = parseInt(everyN, 10)
      body.every_n_months = Number.isFinite(n) && n > 0 ? n : 1
    }
    if (showDueMonth) {
      // Empty selection clears the anchor (back to an even spread).
      const m = parseInt(dueMonth, 10)
      body.month_of_year = Number.isFinite(m) && m >= 1 && m <= 12 ? m : null
    }
    setTarget.mutate({ id: category.id, body }, { onSuccess: onClose })
  }

  const handleClear = () => {
    deleteTarget.mutate(category.id, { onSuccess: onClose })
  }

  const pending = setTarget.isPending || deleteTarget.isPending

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-label={`Edit target for ${category.name}`}
      className="absolute right-0 z-20 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-3 text-left shadow-lg"
    >
      <div className="flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Amount ($)
          <input
            type="text"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-200"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Cadence
          <select
            value={cadence}
            onChange={(e) => setCadence(e.target.value as Cadence)}
            className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-200"
          >
            {CADENCES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        {cadence === 'custom' && (
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Every N months
            <input
              type="number"
              min={1}
              value={everyN}
              onChange={(e) => setEveryN(e.target.value)}
              className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-200"
            />
          </label>
        )}

        {showDueMonth && (
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Due by (month)
            <select
              aria-label="Due month"
              value={dueMonth}
              onChange={(e) => setDueMonth(e.target.value)}
              className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-200"
            >
              <option value="">No due date (spread evenly)</option>
              {MONTHS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            <span className="text-[11px] font-normal text-slate-400">
              Funds the remaining amount evenly across the months up to this one.
            </span>
          </label>
        )}

        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Mode
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
            className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-200"
          >
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>

        {error && (
          <span role="alert" className="text-xs text-rose-600">
            {error}
          </span>
        )}

        <div className="mt-1 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={handleClear}
            disabled={pending || category.target_amount == null}
            className="rounded px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-40"
          >
            Clear target
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={pending}
              className="rounded bg-emerald-600 px-2 py-1 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Target cell — shows the funding target amount (if any) and an "underfunded"
 * badge when this month still needs money to hit the target.
 *
 * When the target is satisfied for the month (underfunded === 0) we only claim
 * "Funded ✓" for the truly-funded case: a monthly cadence, or a non-monthly
 * cadence whose envelope balance already meets the full target amount. For
 * non-monthly cadences in a non-anchor month (where nothing is owed yet but the
 * envelope isn't full) we show a neutral "On track" label instead, so a yearly
 * target doesn't misleadingly read as "Funded" eleven months of the year.
 *
 * The whole cell is a button that opens a compact inline {@link TargetEditor}
 * to create, edit, or clear the target.
 */
function TargetCell({ category }: { category: CategoryState }) {
  const [editing, setEditing] = useState(false)
  const under = category.underfunded

  const trulyFunded =
    under === 0 &&
    (category.target_cadence === 'monthly' ||
      category.target_amount == null ||
      category.available >= category.target_amount)

  return (
    <div className="relative flex flex-col items-end gap-0.5">
      <button
        type="button"
        aria-label={`Edit target for ${category.name}`}
        onClick={() => setEditing(true)}
        className="flex flex-col items-end gap-0.5 rounded px-1 py-0.5 hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-200"
      >
        {category.target_amount == null ? (
          <span className="text-xs text-slate-300">Set target</span>
        ) : (
          <>
            <span className="text-xs tabular-nums text-slate-500">
              {formatMoney(category.target_amount)}
              {category.target_cadence && category.target_cadence !== 'monthly'
                ? ` /${category.target_cadence}`
                : ''}
            </span>
            {under > 0 ? (
              <span
                data-testid={`underfunded-${category.id}`}
                className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-amber-200"
              >
                {formatMoney(under)} underfunded
              </span>
            ) : trulyFunded ? (
              <span className="text-xs font-semibold text-emerald-600">
                Funded ✓
              </span>
            ) : (
              <span className="text-xs font-medium text-slate-500">
                On track
              </span>
            )}
          </>
        )}
      </button>

      {editing && (
        <TargetEditor
          category={category}
          onClose={() => setEditing(false)}
        />
      )}
    </div>
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
          <span className="flex items-center gap-2">
            <span className="text-sm text-slate-800">{info.getValue()}</span>
            {info.row.original.is_payment && (
              <span
                data-testid={`payment-badge-${info.row.original.id}`}
                className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-700 ring-1 ring-sky-200"
              >
                Payment
              </span>
            )}
          </span>
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
      columnHelper.display({
        id: 'target',
        header: 'Target',
        cell: (info) => <TargetCell category={info.row.original} />,
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
                className="px-3 py-2 text-left text-sm font-semibold text-slate-700"
              >
                {group.name}
              </th>
              <td className="px-3 py-2 text-right text-sm font-semibold tabular-nums text-slate-500">
                {formatMoney(subtotal)}
              </td>
              {/* Empty cells under Activity / Available / Target. */}
              <td colSpan={columnCount - 2} />
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
