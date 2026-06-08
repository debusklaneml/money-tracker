// CategoryDeepDive — pick a category and inspect its transactions.
//
// The select lists non-hidden categories. Once a category is chosen we query
// its transactions and render date | payee | amount plus a summed total.

import { useMemo, useState } from 'react'

import { useTransactions } from '../../lib/queries'
import { formatMoney } from '../../lib/money'
import type { Category } from '../../lib/types'

interface CategoryDeepDiveProps {
  categories: Category[]
}

export default function CategoryDeepDive({ categories }: CategoryDeepDiveProps) {
  const [categoryId, setCategoryId] = useState<string>('')

  const visibleCategories = useMemo(
    () => categories.filter((c) => !c.hidden),
    [categories],
  )

  // The query is only meaningful once a category is selected. Gate the FETCH
  // (not just rendering) with `enabled`, otherwise an unfiltered fetch-all
  // would fire on mount before the user picks anything.
  const { data, isLoading } = useTransactions(
    categoryId ? { category_id: categoryId } : undefined,
    { enabled: !!categoryId },
  )

  const transactions = categoryId ? (data ?? []) : []

  const total = useMemo(
    () => transactions.reduce((sum, t) => sum + t.amount, 0),
    [transactions],
  )

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">
          Category deep-dive
        </h2>
        <select
          aria-label="Deep-dive category"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-200"
        >
          <option value="">Select a category…</option>
          {visibleCategories.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.category_group_name
                ? `${cat.category_group_name} · ${cat.name}`
                : cat.name}
            </option>
          ))}
        </select>
      </div>

      {!categoryId ? (
        <p className="mt-4 text-sm text-slate-500">
          Pick a category above to see its transactions.
        </p>
      ) : isLoading ? (
        <p className="mt-4 text-sm text-slate-500">Loading transactions…</p>
      ) : transactions.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">
          No transactions in this category.
        </p>
      ) : (
        <>
          <table
            data-testid="deep-dive-table"
            className="mt-4 w-full border-collapse text-left"
          >
            <thead>
              <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
                <th scope="col" className="px-3 py-2 text-left">
                  Date
                </th>
                <th scope="col" className="px-3 py-2 text-left">
                  Payee
                </th>
                <th scope="col" className="px-3 py-2 text-right">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr
                  key={txn.id}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
                >
                  <td className="px-3 py-2 text-left text-sm tabular-nums text-slate-500">
                    {txn.date}
                  </td>
                  <td className="px-3 py-2 text-left text-sm text-slate-800">
                    {txn.payee_name ?? 'Unknown'}
                  </td>
                  <td
                    className={
                      'px-3 py-2 text-right text-sm tabular-nums ' +
                      (txn.amount < 0 ? 'text-slate-800' : 'text-emerald-600')
                    }
                  >
                    {formatMoney(txn.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-slate-200">
                <td
                  colSpan={2}
                  className="px-3 py-2 text-left text-sm font-semibold text-slate-700"
                >
                  Total
                </td>
                <td
                  data-testid="deep-dive-total"
                  className="px-3 py-2 text-right text-sm font-semibold tabular-nums text-slate-900"
                >
                  {formatMoney(total)}
                </td>
              </tr>
            </tfoot>
          </table>
        </>
      )}
    </section>
  )
}
