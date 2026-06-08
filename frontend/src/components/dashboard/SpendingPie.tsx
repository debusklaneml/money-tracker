// SpendingPie — spending-by-category donut for the current window.
//
// Sources useSpendingByCategory(1). Slices are keyed by category_name
// (null → "Uncategorized"). recharts values are DOLLARS (toDisplay); tooltips
// format the original milliunit value with formatMoney.

import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

import { useSpendingByCategory } from '../../lib/queries'
import { formatMoney, toDisplay } from '../../lib/money'

// A rotating palette of slate/emerald-leaning hues.
const COLORS = [
  '#10b981', // emerald-500
  '#0ea5e9', // sky-500
  '#6366f1', // indigo-500
  '#f59e0b', // amber-500
  '#ec4899', // pink-500
  '#14b8a6', // teal-500
  '#8b5cf6', // violet-500
  '#ef4444', // red-500
  '#84cc16', // lime-500
  '#64748b', // slate-500
]

export default function SpendingPie() {
  const { data, isLoading } = useSpendingByCategory(1)

  const rows = data ?? []

  const chartData = rows.map((row) => ({
    name: row.category_name ?? 'Uncategorized',
    value: toDisplay(row.total_amount),
    milliunits: row.total_amount,
  }))

  return (
    <div
      data-testid="spending-pie"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-700">
        Spending by Category
      </h2>

      {isLoading ? (
        <div className="mt-4 h-[260px] animate-pulse rounded bg-slate-100" />
      ) : chartData.length === 0 ? (
        <div className="mt-4 flex h-[260px] items-center justify-center text-sm text-slate-400">
          No spending yet
        </div>
      ) : (
        <div className="mt-2">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={(entry) => entry.name}
              >
                {chartData.map((entry, index) => (
                  <Cell
                    key={entry.name}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                formatter={(_value, _name, item) =>
                  formatMoney(item?.payload?.milliunits ?? 0)
                }
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
