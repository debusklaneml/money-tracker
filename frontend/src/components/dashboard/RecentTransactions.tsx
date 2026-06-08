// RecentTransactions — small table of the 8 most recent transactions.
//
// Sources useTransactions({ limit: 8 }). Columns: Date, Payee, Category,
// Amount (formatMoney, negative styled rose). Handles loading and empty states.

import { useTransactions } from '../../lib/queries'
import { formatMoney } from '../../lib/money'

export default function RecentTransactions() {
  const { data, isLoading } = useTransactions({ limit: 8 })

  const transactions = data ?? []

  return (
    <div
      data-testid="recent-transactions"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-700">
        Recent Transactions
      </h2>

      {isLoading ? (
        <div className="mt-4 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-6 animate-pulse rounded bg-slate-100"
            />
          ))}
        </div>
      ) : transactions.length === 0 ? (
        <div className="mt-4 text-sm text-slate-400">No transactions yet</div>
      ) : (
        <table className="mt-3 w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <th scope="col" className="px-2 py-2 text-left">
                Date
              </th>
              <th scope="col" className="px-2 py-2 text-left">
                Payee
              </th>
              <th scope="col" className="px-2 py-2 text-left">
                Category
              </th>
              <th scope="col" className="px-2 py-2 text-right">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((txn) => {
              const negative = txn.amount < 0
              return (
                <tr
                  key={txn.id}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
                >
                  <td className="px-2 py-2 text-sm tabular-nums text-slate-500">
                    {txn.date}
                  </td>
                  <td className="px-2 py-2 text-sm text-slate-800">
                    {txn.payee_name ?? '—'}
                  </td>
                  <td className="px-2 py-2 text-sm text-slate-500">
                    {txn.category_name ?? 'Uncategorized'}
                  </td>
                  <td
                    data-negative={negative}
                    className={
                      'px-2 py-2 text-right text-sm font-medium tabular-nums ' +
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
      )}
    </div>
  )
}
