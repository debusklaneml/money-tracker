// MonthlyTrendChart — bar chart of total spending per month over the last year.
//
// Sources useMonthlyTrend(12). x = month ('YYYY-MM'), y = dollars
// (toDisplay(total_amount)). Tooltip formats the milliunit value with
// formatMoney.

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { useMonthlyTrend } from '../../lib/queries'
import { formatMoney, toDisplay } from '../../lib/money'

export default function MonthlyTrendChart() {
  const { data, isLoading } = useMonthlyTrend(12)

  const rows = data ?? []

  const chartData = rows.map((row) => ({
    month: row.month,
    value: toDisplay(row.total_amount),
    milliunits: row.total_amount,
  }))

  return (
    <div
      data-testid="monthly-trend"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-700">Monthly Spending</h2>

      {isLoading ? (
        <div className="mt-4 h-[260px] animate-pulse rounded bg-slate-100" />
      ) : chartData.length === 0 ? (
        <div className="mt-4 flex h-[260px] items-center justify-center text-sm text-slate-400">
          No trend data yet
        </div>
      ) : (
        <div className="mt-2">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="month"
                tick={{ fontSize: 12, fill: '#64748b' }}
              />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
              <Tooltip
                formatter={(_value, _name, item) =>
                  formatMoney(item?.payload?.milliunits ?? 0)
                }
              />
              <Bar dataKey="value" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
