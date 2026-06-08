// TransactionTable — a semantic table of transactions with per-row selection
// checkboxes, a select-all header checkbox, and an inline per-row category
// <select> for single-row categorization. Uncategorized rows are subtly
// highlighted; outflow amounts (negative) render red.

import type { Category, Transaction } from '../../lib/types'
import { formatMoney } from '../../lib/money'

interface TransactionTableProps {
  transactions: Transaction[]
  categories: Category[]
  selectedIds: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
  onCategorizeRow: (
    id: string,
    categoryId: string | null,
    categoryName: string | null,
  ) => void
}

export default function TransactionTable({
  transactions,
  categories,
  selectedIds,
  onToggle,
  onToggleAll,
  onCategorizeRow,
}: TransactionTableProps) {
  const allSelected =
    transactions.length > 0 && selectedIds.size === transactions.length
  const someSelected = selectedIds.size > 0 && !allSelected

  return (
    <table
      data-testid="transaction-table"
      className="w-full border-collapse text-left"
    >
      <thead>
        <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <th scope="col" className="px-3 py-2">
            <input
              type="checkbox"
              aria-label="Select all transactions"
              className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-200"
              checked={allSelected}
              ref={(el) => {
                if (el) el.indeterminate = someSelected
              }}
              onChange={onToggleAll}
            />
          </th>
          <th scope="col" className="px-3 py-2">
            Date
          </th>
          <th scope="col" className="px-3 py-2">
            Payee
          </th>
          <th scope="col" className="px-3 py-2">
            Memo
          </th>
          <th scope="col" className="px-3 py-2">
            Account
          </th>
          <th scope="col" className="px-3 py-2 text-right">
            Amount
          </th>
          <th scope="col" className="px-3 py-2">
            Category
          </th>
        </tr>
      </thead>

      <tbody>
        {transactions.map((txn) => {
          const selected = selectedIds.has(txn.id)
          const uncategorized = txn.category_id == null
          const negative = txn.amount < 0
          return (
            <tr
              key={txn.id}
              data-uncategorized={uncategorized}
              className={
                'border-b border-slate-100 last:border-0 hover:bg-slate-50/60 ' +
                (selected
                  ? 'bg-emerald-50/60 '
                  : uncategorized
                    ? 'bg-amber-50/50 '
                    : '')
              }
            >
              <td className="px-3 py-2 align-middle">
                <input
                  type="checkbox"
                  aria-label={`Select transaction ${txn.id}`}
                  className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-200"
                  checked={selected}
                  onChange={() => onToggle(txn.id)}
                />
              </td>
              <td className="px-3 py-2 align-middle text-sm tabular-nums text-slate-600">
                {txn.date}
              </td>
              <td className="px-3 py-2 align-middle text-sm text-slate-800">
                {txn.payee_name ?? '—'}
              </td>
              <td className="px-3 py-2 align-middle text-sm text-slate-500">
                {txn.memo ?? ''}
              </td>
              <td className="px-3 py-2 align-middle text-sm text-slate-600">
                {txn.account_name ?? '—'}
              </td>
              <td
                data-negative={negative}
                className={
                  'px-3 py-2 align-middle text-right text-sm font-medium tabular-nums ' +
                  (negative ? 'text-rose-600' : 'text-slate-800')
                }
              >
                {formatMoney(txn.amount)}
              </td>
              <td className="px-3 py-2 align-middle">
                <select
                  aria-label={`Category for transaction ${txn.id}`}
                  className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
                  value={txn.category_id ?? ''}
                  onChange={(e) => {
                    const nextId = e.target.value === '' ? null : e.target.value
                    const name =
                      nextId === null
                        ? null
                        : (categories.find((c) => c.id === nextId)?.name ??
                          null)
                    onCategorizeRow(txn.id, nextId, name)
                  }}
                >
                  <option value="">—</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.category_group_name
                        ? `${category.category_group_name}: ${category.name}`
                        : category.name}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
