// SpendingBreakdown — category spending breakdown for the active time window.
//
// Renders a bar chart of spend-by-category plus a table (Category | Spent |
// # txns | % of total), sorted descending by amount. All money values arrive
// as POSITIVE milliunits of outflow.

import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatMoney, toDisplay } from '../../lib/money'
import type { SpendingByCategory } from '../../lib/types'

interface SpendingBreakdownProps {
  data: SpendingByCategory[]
}

export default function SpendingBreakdown({ data }: SpendingBreakdownProps) {
  const rows = useMemo(() => {
    const sorted = [...data].sort((a, b) => b.total_amount - a.total_amount)
    const total = sorted.reduce((sum, r) => sum + r.total_amount, 0)
    return sorted.map((r) => ({
      categoryId: r.category_id,
      name: r.category_name ?? 'Uncategorized',
      total: r.total_amount,
      count: r.transaction_count,
      pct: total > 0 ? (r.total_amount / total) * 100 : 0,
      // Chart values must be DOLLARS.
      dollars: toDisplay(r.total_amount),
    }))
  }, [data])

  if (rows.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-slate-900">
          Spending by category
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          No spending in this window yet.
        </p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-slate-900">
        Spending by category
      </h2>

      <div data-testid="breakdown-chart" className="mt-4">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(_value, _name, item) =>
                formatMoney(Number(item?.payload?.total ?? 0))
              }
            />
            <Bar dataKey="dollars" name="Spent" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <table
        data-testid="breakdown-table"
        className="mt-6 w-full border-collapse text-left"
      >
        <thead>
          <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <th scope="col" className="px-3 py-2 text-left">
              Category
            </th>
            <th scope="col" className="px-3 py-2 text-right">
              Spent
            </th>
            <th scope="col" className="px-3 py-2 text-right">
              # txns
            </th>
            <th scope="col" className="px-3 py-2 text-right">
              % of total
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.categoryId ?? 'uncategorized'}
              className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
            >
              <td className="px-3 py-2 text-left text-sm text-slate-800">
                {row.name}
              </td>
              <td className="px-3 py-2 text-right text-sm tabular-nums text-slate-800">
                {formatMoney(row.total)}
              </td>
              <td className="px-3 py-2 text-right text-sm tabular-nums text-slate-500">
                {row.count}
              </td>
              <td className="px-3 py-2 text-right text-sm tabular-nums text-slate-500">
                {row.pct.toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
