// MoveMoneyPanel — a modal dialog for moving budgeted money between categories.
//
// The canonical use is covering an overspent envelope (negative Available) by
// pulling surplus from another. Picks a source ("From") and destination ("To")
// category, an amount, and fires the existing useMove() mutation (which already
// invalidates the budget query on success).

import { useEffect, useMemo, useState } from 'react'

import { useBudget, useMove } from '../../lib/queries'
import { formatMoney, parseMoneyInput, toInputString } from '../../lib/money'
import type { CategoryState } from '../../lib/types'

interface MoveMoneyPanelProps {
  open: boolean
  onClose: () => void
  month?: string
  /** Preselect the destination — e.g. an overspent category needing cover. */
  defaultToId?: string
  /** Preselect the source. */
  defaultFromId?: string
}

const optionLabel = (c: CategoryState) => `${c.group} › ${c.name}`

export default function MoveMoneyPanel({
  open,
  onClose,
  month,
  defaultToId,
  defaultFromId,
}: MoveMoneyPanelProps) {
  const { data } = useBudget(month)
  const move = useMove()

  const categories = useMemo<CategoryState[]>(
    () => data?.categories ?? [],
    [data],
  )

  const [fromId, setFromId] = useState(defaultFromId ?? '')
  const [toId, setToId] = useState(defaultToId ?? '')
  const [amountText, setAmountText] = useState('')

  // Re-seed selections each time the panel is (re)opened so it reflects the
  // latest preselection (e.g. opened from a specific overspent category).
  useEffect(() => {
    if (open) {
      setFromId(defaultFromId ?? '')
      setToId(defaultToId ?? '')
      setAmountText('')
    }
  }, [open, defaultFromId, defaultToId])

  if (!open) return null

  const fromCat = categories.find((c) => c.id === fromId)
  const toCat = categories.find((c) => c.id === toId)

  const parsedAmount = parseMoneyInput(amountText)
  const sameCategory = fromId !== '' && fromId === toId
  const amountInvalid = parsedAmount === null || parsedAmount <= 0
  const missingSelection = fromId === '' || toId === ''

  const canSubmit = !sameCategory && !amountInvalid && !missingSelection

  // The destination's shortfall, if it is overspent (negative Available).
  const shortfall =
    toCat && toCat.available < 0 ? -toCat.available : 0

  const validationMessage = (() => {
    if (sameCategory) return 'Pick two different categories.'
    if (amountText.trim() !== '' && amountInvalid)
      return 'Enter an amount greater than zero.'
    return null
  })()

  const handleMove = () => {
    if (!canSubmit || parsedAmount === null) return
    move.mutate({
      from_id: fromId,
      to_id: toId,
      amount: parsedAmount,
      month: month ?? null,
    })
    onClose()
  }

  const handleCover = () => {
    if (shortfall > 0) {
      setAmountText(toInputString(shortfall))
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Move money"
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-800">Move money</h2>
        <p className="mt-1 text-sm text-slate-500">
          Move budgeted money from one category to another.
        </p>

        <div className="mt-5 space-y-4">
          {/* From */}
          <div>
            <label
              htmlFor="move-from"
              className="block text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              From
            </label>
            <select
              id="move-from"
              aria-label="Move from"
              value={fromId}
              onChange={(e) => setFromId(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
            >
              <option value="">Select a category…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {optionLabel(c)}
                </option>
              ))}
            </select>
            {fromCat && (
              <p className="mt-1 text-xs text-slate-500">
                Available:{' '}
                <span
                  className={
                    'tabular-nums ' +
                    (fromCat.available < 0
                      ? 'text-rose-600'
                      : 'text-emerald-600')
                  }
                >
                  {formatMoney(fromCat.available)}
                </span>
              </p>
            )}
          </div>

          {/* To */}
          <div>
            <label
              htmlFor="move-to"
              className="block text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              To
            </label>
            <select
              id="move-to"
              aria-label="Move to"
              value={toId}
              onChange={(e) => setToId(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
            >
              <option value="">Select a category…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {optionLabel(c)}
                </option>
              ))}
            </select>
            {toCat && (
              <p className="mt-1 text-xs text-slate-500">
                Available:{' '}
                <span
                  className={
                    'tabular-nums ' +
                    (toCat.available < 0
                      ? 'text-rose-600'
                      : 'text-emerald-600')
                  }
                >
                  {formatMoney(toCat.available)}
                </span>
              </p>
            )}
            {shortfall > 0 && (
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="text-xs text-rose-600">
                  Needs {formatMoney(shortfall)} to cover
                </span>
                <button
                  type="button"
                  onClick={handleCover}
                  className="rounded border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                >
                  Cover overspending
                </button>
              </div>
            )}
          </div>

          {/* Amount */}
          <div>
            <label
              htmlFor="move-amount"
              className="block text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              Amount
            </label>
            <input
              id="move-amount"
              type="text"
              inputMode="decimal"
              aria-label="Amount to move"
              value={amountText}
              onChange={(e) => setAmountText(e.target.value)}
              placeholder="0.00"
              className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
            />
          </div>

          {validationMessage && (
            <p className="text-xs text-rose-600">{validationMessage}</p>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleMove}
            disabled={!canSubmit || move.isPending}
            className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {move.isPending ? 'Moving…' : 'Move'}
          </button>
        </div>
      </div>
    </div>
  )
}
