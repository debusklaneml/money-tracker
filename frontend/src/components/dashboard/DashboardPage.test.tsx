import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import DashboardPage from '../../routes/DashboardPage'
import {
  useAlerts,
  useBudget,
  useMonthlyTrend,
  useSettingsSummary,
  useSpendingByCategory,
  useTransactions,
} from '../../lib/queries'
import type {
  Alert,
  MonthlyTrendPoint,
  SettingsSummary,
  SpendingByCategory,
  Transaction,
} from '../../lib/types'

// Mock every spine hook the page uses so the dashboard renders deterministically
// with no network. recharts renders nothing measurable in jsdom — we only
// assert on the surrounding (non-chart) UI.
vi.mock('../../lib/queries', () => ({
  useSettingsSummary: vi.fn(),
  useBudget: vi.fn(),
  useSpendingByCategory: vi.fn(),
  useMonthlyTrend: vi.fn(),
  useTransactions: vi.fn(),
  useAlerts: vi.fn(),
}))

const mockSettings = vi.mocked(useSettingsSummary)
const mockBudget = vi.mocked(useBudget)
const mockSpending = vi.mocked(useSpendingByCategory)
const mockTrend = vi.mocked(useMonthlyTrend)
const mockTransactions = vi.mocked(useTransactions)
const mockAlerts = vi.mocked(useAlerts)

const summary: SettingsSummary = {
  account_count: 4,
  category_count: 22,
  transaction_count: 318,
  uncategorized_count: 7,
  rule_count: 9,
  active_alert_count: 2,
  current_month: '2026-06-01',
  ready_to_assign: 125000,
  db_path: '/tmp/bud.db',
}

const spending: SpendingByCategory[] = [
  {
    category_id: 'c1',
    category_name: 'Groceries',
    total_amount: 45000,
    transaction_count: 12,
  },
  {
    category_id: 'c2',
    category_name: 'Dining',
    total_amount: 22000,
    transaction_count: 8,
  },
  {
    category_id: null,
    category_name: null,
    total_amount: 5000,
    transaction_count: 2,
  },
]

const trend: MonthlyTrendPoint[] = [
  { month: '2026-04', total_amount: 90000 },
  { month: '2026-05', total_amount: 110000 },
  { month: '2026-06', total_amount: 72000 },
]

const transactions: Transaction[] = [
  {
    id: 't1',
    account_id: 'a1',
    account_name: 'Checking',
    date: '2026-06-05',
    amount: -4500,
    memo: null,
    cleared: 'cleared',
    approved: true,
    flag_color: null,
    payee_id: null,
    payee_name: 'Whole Foods',
    category_id: 'c1',
    category_name: 'Groceries',
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
  },
  {
    id: 't2',
    account_id: 'a1',
    account_name: 'Checking',
    date: '2026-06-04',
    amount: 250000,
    memo: null,
    cleared: 'cleared',
    approved: true,
    flag_color: null,
    payee_id: null,
    payee_name: 'Paycheck',
    category_id: null,
    category_name: null,
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
  },
]

const alerts: Alert[] = [
  {
    id: 1,
    alert_type: 'overspent',
    severity: 'critical',
    title: 'Dining is overspent',
    description: 'You spent more than assigned.',
    related_entity_id: null,
    related_entity_type: null,
    metadata: null,
    created_at: '2026-06-01T00:00:00Z',
    acknowledged_at: null,
    dismissed: false,
  },
  {
    id: 2,
    alert_type: 'low_balance',
    severity: 'warning',
    title: 'Checking balance is low',
    description: null,
    related_entity_id: null,
    related_entity_type: null,
    metadata: null,
    created_at: '2026-06-02T00:00:00Z',
    acknowledged_at: null,
    dismissed: false,
  },
  {
    id: 3,
    alert_type: 'stale',
    severity: 'info',
    title: 'Dismissed alert',
    description: null,
    related_entity_id: null,
    related_entity_type: null,
    metadata: null,
    created_at: '2026-05-01T00:00:00Z',
    acknowledged_at: null,
    dismissed: true,
  },
]

function seed({
  settingsData = summary,
  settingsLoading = false,
  budgetData = { ready_to_assign: summary.ready_to_assign },
  spendingData = spending,
  trendData = trend,
  txnData = transactions,
  txnLoading = false,
  alertsData = alerts,
}: {
  settingsData?: SettingsSummary | undefined
  settingsLoading?: boolean
  budgetData?: { ready_to_assign: number } | undefined
  spendingData?: SpendingByCategory[]
  trendData?: MonthlyTrendPoint[]
  txnData?: Transaction[]
  txnLoading?: boolean
  alertsData?: Alert[]
} = {}) {
  mockSettings.mockReturnValue({
    data: settingsData,
    isLoading: settingsLoading,
  } as ReturnType<typeof useSettingsSummary>)
  mockBudget.mockReturnValue({
    data: budgetData,
  } as ReturnType<typeof useBudget>)
  mockSpending.mockReturnValue({
    data: spendingData,
    isLoading: false,
  } as ReturnType<typeof useSpendingByCategory>)
  mockTrend.mockReturnValue({
    data: trendData,
    isLoading: false,
  } as ReturnType<typeof useMonthlyTrend>)
  mockTransactions.mockReturnValue({
    data: txnData,
    isLoading: txnLoading,
  } as ReturnType<typeof useTransactions>)
  mockAlerts.mockReturnValue({
    data: alertsData,
  } as ReturnType<typeof useAlerts>)
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('DashboardPage', () => {
  it('renders the heading and metric cards with summary values', () => {
    seed()
    renderPage()

    expect(
      screen.getByRole('heading', { name: 'Dashboard' }),
    ).toBeInTheDocument()

    // Ready to Assign formatted as money.
    expect(
      within(screen.getByTestId('metric-ready_to_assign')).getByText('$125.00'),
    ).toBeInTheDocument()

    // Counts.
    expect(
      within(screen.getByTestId('metric-accounts')).getByText('4'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('metric-categories')).getByText('22'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('metric-transactions')).getByText('318'),
    ).toBeInTheDocument()
    // Uncategorized count surfaced.
    expect(
      within(screen.getByTestId('metric-uncategorized')).getByText('7'),
    ).toBeInTheDocument()
    // Active alerts count surfaced.
    expect(
      within(screen.getByTestId('metric-active_alerts')).getByText('2'),
    ).toBeInTheDocument()
  })

  it('shows skeleton metric cards while the summary is loading', () => {
    seed({ settingsData: undefined, settingsLoading: true })
    renderPage()

    expect(screen.getByTestId('metric-cards-loading')).toBeInTheDocument()
    expect(screen.queryByTestId('metric-accounts')).not.toBeInTheDocument()
  })

  it('renders recent transaction rows with a negative-styled amount', () => {
    seed()
    renderPage()

    const table = screen.getByTestId('recent-transactions')
    expect(within(table).getByText('Whole Foods')).toBeInTheDocument()
    expect(within(table).getByText('Paycheck')).toBeInTheDocument()

    // Outflow formatted and negative-styled.
    const outflow = within(table).getByText('-$4.50')
    expect(outflow).toBeInTheDocument()
    expect(outflow).toHaveAttribute('data-negative', 'true')

    // Inflow not negative-styled.
    const inflow = within(table).getByText('$250.00')
    expect(inflow).toHaveAttribute('data-negative', 'false')
  })

  it('surfaces uncategorized count and active alerts in the attention list', () => {
    seed()
    renderPage()

    const list = screen.getByTestId('attention-list')
    expect(
      within(list).getByText(/7 uncategorized transactions/i),
    ).toBeInTheDocument()

    // Active alert titles appear; dismissed one does not.
    expect(within(list).getByText('Dining is overspent')).toBeInTheDocument()
    expect(
      within(list).getByText('Checking balance is low'),
    ).toBeInTheDocument()
    expect(within(list).queryByText('Dismissed alert')).not.toBeInTheDocument()

    // The uncategorized item links to /transactions.
    const link = within(list).getByRole('link', {
      name: /7 uncategorized transactions/i,
    })
    expect(link).toHaveAttribute('href', '/transactions')
  })

  it('shows the all-clear state when nothing needs attention', () => {
    seed({
      settingsData: { ...summary, uncategorized_count: 0 },
      alertsData: [],
    })
    renderPage()

    const list = screen.getByTestId('attention-list')
    expect(within(list).getByText(/all clear/i)).toBeInTheDocument()
  })

  it('renders empty states without crashing when there is no data', () => {
    seed({
      spendingData: [],
      trendData: [],
      txnData: [],
    })
    renderPage()

    expect(
      within(screen.getByTestId('spending-pie')).getByText(/no spending yet/i),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('monthly-trend')).getByText(/no trend data/i),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('recent-transactions')).getByText(
        /no transactions yet/i,
      ),
    ).toBeInTheDocument()
  })
})
