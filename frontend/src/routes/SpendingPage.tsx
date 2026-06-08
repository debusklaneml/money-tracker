// SpendingPage — the spending-analysis cockpit.
//
// A time-window selector (1 / 3 / 6 / 12 months) drives the category breakdown.
// The monthly trend always shows the trailing 12 months, top payees are derived
// in memory from a generous transaction page, and the deep-dive manages its own
// category selection + query.

import { useState } from 'react'

import {
  useCategories,
  useMonthlyTrend,
  useSpendingByCategory,
  useTransactions,
} from '../lib/queries'
import SpendingBreakdown from '../components/spending/SpendingBreakdown'
import MonthlyTrendWithAverage from '../components/spending/MonthlyTrendWithAverage'
import TopPayees from '../components/spending/TopPayees'
import CategoryDeepDive from '../components/spending/CategoryDeepDive'

const WINDOW_OPTIONS: { months: number; label: string }[] = [
  { months: 1, label: 'This month' },
  { months: 3, label: '3 months' },
  { months: 6, label: '6 months' },
  { months: 12, label: '12 months' },
]

export default function SpendingPage() {
  const [months, setMonths] = useState(1)

  const spending = useSpendingByCategory(months)
  const trend = useMonthlyTrend(12)
  const transactions = useTransactions({ limit: 500 })
  const categories = useCategories()

  return (
    <section className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Spending Analysis</h1>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Window
          <select
            aria-label="Time window"
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-200"
          >
            {WINDOW_OPTIONS.map((opt) => (
              <option key={opt.months} value={opt.months}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <SpendingBreakdown data={spending.data ?? []} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <MonthlyTrendWithAverage data={trend.data ?? []} />
        <TopPayees transactions={transactions.data ?? []} />
      </div>

      <CategoryDeepDive categories={categories.data ?? []} />
    </section>
  )
}
