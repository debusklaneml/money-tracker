import { Routes, Route } from 'react-router-dom'
import AppShell from './components/AppShell'
import BudgetPage from './routes/BudgetPage'
import TransactionsPage from './routes/TransactionsPage'
import ImportPage from './routes/ImportPage'
import CategoriesPage from './routes/CategoriesPage'
import DashboardPage from './routes/DashboardPage'
import SpendingPage from './routes/SpendingPage'
import AlertsPage from './routes/AlertsPage'
import RulesPage from './routes/RulesPage'
import SettingsPage from './routes/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<BudgetPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="spending" element={<SpendingPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="rules" element={<RulesPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<div className="p-8">Not found</div>} />
      </Route>
    </Routes>
  )
}
