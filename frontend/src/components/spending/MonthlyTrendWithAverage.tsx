// MonthlyTrendWithAverage — a bar chart of monthly spending totals with a
// reference line at the mean, plus the average shown as text.
//
// Money arrives as POSITIVE milliunits; chart values are mapped to DOLLARS.

import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatMoney, toDisplay } from '../../lib/money'
import type { MonthlyTrendPoint } from '../../lib/types'

interface MonthlyTrendWithAverageProps {
  data: MonthlyTrendPoint[]
}

export default function MonthlyTrendWithAverage({
  data,
}: MonthlyTrendWithAverageProps) {
  const { rows, averageMilliunits } = useMemo(() => {
    const sorted = [...data].sort((a, b) => a.month.localeCompare(b.month))
    const sum = sorted.reduce((acc, p) => acc + p.total_amount, 0)
    const avg = sorted.length > 0 ? sum / sorted.length : 0
    return {
      rows: sorted.map((p) => ({
        month: p.month,
        dollars: toDisplay(p.total_amount),
      })),
      averageMilliunits: avg,
    }
  }, [data])

  if (rows.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-slate-900">Monthly trend</h2>
        <p className="mt-2 text-sm text-slate-500">No trend data yet.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Monthly trend</h2>
        <p className="text-sm text-slate-500">
          Average:{' '}
          <span
            data-testid="trend-average"
            className="font-semibold tabular-nums text-slate-800"
          >
            {formatMoney(averageMilliunits)}
          </span>
        </p>
      </div>

      <div data-testid="trend-chart" className="mt-4">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value) => formatMoney(Number(value) * 1000)} />
            <ReferenceLine
              y={toDisplay(averageMilliunits)}
              stroke="#f59e0b"
              strokeDasharray="4 4"
              label={{ value: 'avg', position: 'right', fontSize: 11 }}
            />
            <Bar dataKey="dollars" name="Spent" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
