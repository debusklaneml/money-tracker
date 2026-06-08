// TopPayees — derives top spending payees in memory from a transaction list.
//
// There is no backend payee endpoint, so we aggregate OUTFLOWS (amount < 0)
// by payee_name (null → "Unknown"), summing the absolute milliunit amounts,
// then rank descending and take the top `limit` (default 10).

import { useMemo } from 'react'

import { formatMoney } from '../../lib/money'
import type { Transaction } from '../../lib/types'

interface TopPayeesProps {
  transactions: Transaction[]
  limit?: number
}

export default function TopPayees({ transactions, limit }: TopPayeesProps) {
  const top = limit ?? 10

  const payees = useMemo(() => {
    const byPayee = new Map<string, { total: number; count: number }>()
    for (const txn of transactions) {
      // Only outflows count toward "spending".
      if (txn.amount >= 0) continue
      const name = txn.payee_name ?? 'Unknown'
      const entry = byPayee.get(name) ?? { total: 0, count: 0 }
      entry.total += Math.abs(txn.amount)
      entry.count += 1
      byPayee.set(name, entry)
    }
    return Array.from(byPayee.entries())
      .map(([name, { total, count }]) => ({ name, total, count }))
      .sort((a, b) => b.total - a.total)
      .slice(0, top)
  }, [transactions, top])

  if (payees.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-slate-900">Top payees</h2>
        <p className="mt-2 text-sm text-slate-500">No spending yet.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-slate-900">Top payees</h2>
      <ol data-testid="top-payees" className="mt-4 divide-y divide-slate-100">
        {payees.map((payee, idx) => (
          <li
            key={payee.name}
            className="flex items-center justify-between py-2"
          >
            <span className="flex items-center gap-3 text-sm text-slate-800">
              <span className="w-5 text-right tabular-nums text-slate-400">
                {idx + 1}
              </span>
              <span>{payee.name}</span>
            </span>
            <span className="flex items-center gap-4 text-sm">
              <span className="tabular-nums text-slate-500">
                {payee.count} txn{payee.count === 1 ? '' : 's'}
              </span>
              <span className="w-24 text-right font-medium tabular-nums text-slate-900">
                {formatMoney(payee.total)}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
