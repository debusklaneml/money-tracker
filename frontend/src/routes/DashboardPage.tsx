// DashboardPage — the landing dashboard. Composes the metric cards, the
// spending-by-category pie, the monthly trend chart, the recent transactions
// table, and the attention list. Each child sources its own data via the spine
// hooks, so this page is purely layout.

import AttentionList from '../components/dashboard/AttentionList'
import MetricCards from '../components/dashboard/MetricCards'
import MonthlyTrendChart from '../components/dashboard/MonthlyTrendChart'
import RecentTransactions from '../components/dashboard/RecentTransactions'
import SpendingPie from '../components/dashboard/SpendingPie'

export default function DashboardPage() {
  return (
    <section className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>

      <MetricCards />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SpendingPie />
        <MonthlyTrendChart />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecentTransactions />
        </div>
        <AttentionList />
      </div>
    </section>
  )
}
