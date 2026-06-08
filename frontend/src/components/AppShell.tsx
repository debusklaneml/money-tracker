import { NavLink, Link, Outlet } from 'react-router-dom'
import { formatMoney } from '../lib/money'
import { useBudget, useUncategorizedCount } from '../lib/queries'

const NAV_SECTIONS = [
  { to: '/', label: 'Budget', end: true },
  { to: '/transactions', label: 'Transactions' },
  { to: '/import', label: 'Import' },
  { to: '/categories', label: 'Categories' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/rules', label: 'Rules' },
  { to: '/settings', label: 'Settings' },
] as const

function ReadyToAssignBadge() {
  const { data } = useBudget()
  const rta = data?.ready_to_assign

  const loading = rta === undefined
  const negative = !loading && rta < 0

  return (
    <div
      className={[
        'flex flex-col items-end rounded-xl px-4 py-1.5 ring-1',
        loading
          ? 'bg-slate-50 ring-slate-200'
          : negative
            ? 'bg-rose-50 ring-rose-200'
            : 'bg-emerald-50 ring-emerald-200',
      ].join(' ')}
    >
      <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
        Ready to Assign
      </span>
      <span
        className={[
          'text-base font-bold tabular-nums',
          loading
            ? 'text-slate-300'
            : negative
              ? 'text-rose-600'
              : 'text-emerald-600',
        ].join(' ')}
      >
        {loading ? '—' : formatMoney(rta, { withCents: true })}
      </span>
    </div>
  )
}

function UncategorizedBadge() {
  const { data } = useUncategorizedCount()
  const loading = data === undefined
  const count = data ?? 0

  return (
    <Link
      to="/transactions"
      className={[
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
        loading
          ? 'bg-slate-100 text-slate-400'
          : count > 0
            ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
            : 'bg-slate-100 text-slate-500 hover:bg-slate-200',
      ].join(' ')}
      title="Transactions needing a category"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {loading ? '—' : `${count} uncategorized`}
    </Link>
  )
}

export default function AppShell() {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      {/* Sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <Link to="/" className="flex items-center gap-2 px-6 py-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-lg font-black text-emerald-600">
            $
          </span>
          <span className="text-xl font-extrabold tracking-tight text-slate-900">
            BUD
          </span>
        </Link>
        <nav
          aria-label="Main navigation"
          className="flex flex-1 flex-col gap-1 px-3 py-2"
        >
          {NAV_SECTIONS.map((section) => (
            <NavLink
              key={section.to}
              to={section.to}
              end={'end' in section ? section.end : false}
              className={({ isActive }) =>
                [
                  'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                ].join(' ')
              }
            >
              {section.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
          {/* Mobile brand */}
          <Link to="/" className="flex items-center gap-2 md:hidden">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 text-base font-black text-emerald-600">
              $
            </span>
            <span className="text-lg font-extrabold tracking-tight text-slate-900">
              BUD
            </span>
          </Link>
          <div className="hidden md:block" />
          <div className="flex items-center gap-3">
            <UncategorizedBadge />
            <ReadyToAssignBadge />
          </div>
        </header>

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
