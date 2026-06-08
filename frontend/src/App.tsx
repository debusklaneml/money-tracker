import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import AppShell from './components/AppShell'
import BudgetPage from './routes/BudgetPage'
import TransactionsPage from './routes/TransactionsPage'
import ImportPage from './routes/ImportPage'
import CategoriesPage from './routes/CategoriesPage'
import RulesPage from './routes/RulesPage'
import SettingsPage from './routes/SettingsPage'

// The Insights routes pull in recharts (~big). Lazy-load them so recharts is
// code-split into its own chunk and excluded from the initial bundle — it only
// downloads when the user visits Dashboard or Spending.
const DashboardPage = lazy(() => import('./routes/DashboardPage'))
const SpendingPage = lazy(() => import('./routes/SpendingPage'))
const AlertsPage = lazy(() => import('./routes/AlertsPage'))

function RouteFallback() {
  return <div className="p-8 text-sm text-slate-500">Loading…</div>
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<BudgetPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route
          path="dashboard"
          element={
            <Suspense fallback={<RouteFallback />}>
              <DashboardPage />
            </Suspense>
          }
        />
        <Route
          path="spending"
          element={
            <Suspense fallback={<RouteFallback />}>
              <SpendingPage />
            </Suspense>
          }
        />
        <Route
          path="alerts"
          element={
            <Suspense fallback={<RouteFallback />}>
              <AlertsPage />
            </Suspense>
          }
        />
        <Route path="rules" element={<RulesPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<div className="p-8">Not found</div>} />
      </Route>
    </Routes>
  )
}
