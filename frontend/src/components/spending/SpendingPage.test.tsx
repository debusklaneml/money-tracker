import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import SpendingPage from '../../routes/SpendingPage'
import type {
  Category,
  MonthlyTrendPoint,
  SpendingByCategory,
  Transaction,
} from '../../lib/types'

vi.mock('../../lib/queries', () => ({
  useSpendingByCategory: vi.fn(),
  useMonthlyTrend: vi.fn(),
  useTransactions: vi.fn(),
  useCategories: vi.fn(),
}))

import {
  useSpendingByCategory,
  useMonthlyTrend,
  useTransactions,
  useCategories,
} from '../../lib/queries'

const mockedSpending = vi.mocked(useSpendingByCategory)
const mockedTrend = vi.mocked(useMonthlyTrend)
const mockedTransactions = vi.mocked(useTransactions)
const mockedCategories = vi.mocked(useCategories)

// --- Sample data ----------------------------------------------------------

const spendingData: SpendingByCategory[] = [
  // Intentionally out of order to prove the component sorts descending.
  { category_id: 'c2', category_name: 'Dining', total_amount: 30000, transaction_count: 3 },
  { category_id: 'c1', category_name: 'Groceries', total_amount: 90000, transaction_count: 9 },
  { category_id: null, category_name: null, total_amount: 10000, transaction_count: 1 },
]

const trendData: MonthlyTrendPoint[] = [
  { month: '2026-04', total_amount: 100000 },
  { month: '2026-05', total_amount: 200000 },
  { month: '2026-06', total_amount: 300000 },
]
// mean = 600000 / 3 = 200000 → $200.00

function txn(over: Partial<Transaction>): Transaction {
  return {
    id: 'x',
    account_id: 'a1',
    account_name: 'Checking',
    date: '2026-06-01',
    amount: -1000,
    memo: null,
    cleared: 'cleared',
    approved: true,
    flag_color: null,
    payee_id: null,
    payee_name: 'Someone',
    category_id: null,
    category_name: null,
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
    ...over,
  }
}

const transactionData: Transaction[] = [
  // Costco: two outflows summing to -$80.00
  txn({ id: 't1', payee_name: 'Costco', amount: -50000 }),
  txn({ id: 't2', payee_name: 'Costco', amount: -30000 }),
  // Netflix: one outflow of -$15.00
  txn({ id: 't3', payee_name: 'Netflix', amount: -15000 }),
  // An inflow that must be ignored by Top Payees.
  txn({ id: 't4', payee_name: 'Paycheck', amount: 500000 }),
]

const categoryData: Category[] = [
  {
    id: 'c1',
    category_group_id: 'g1',
    category_group_name: 'Everyday',
    name: 'Groceries',
    hidden: false,
    budgeted: 0,
    activity: 0,
    balance: 0,
    goal_type: null,
    goal_target: null,
    goal_target_month: null,
    sort_order: 0,
  },
  {
    id: 'c-hidden',
    category_group_id: 'g1',
    category_group_name: 'Everyday',
    name: 'Old Stuff',
    hidden: true,
    budgeted: 0,
    activity: 0,
    balance: 0,
    goal_type: null,
    goal_target: null,
    goal_target_month: null,
    sort_order: 1,
  },
]

function q<T>(data: T) {
  return { data, isLoading: false, isError: false } as unknown as ReturnType<
    typeof useTransactions
  >
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedSpending.mockReturnValue(q(spendingData) as never)
  mockedTrend.mockReturnValue(q(trendData) as never)
  mockedTransactions.mockReturnValue(q(transactionData) as never)
  mockedCategories.mockReturnValue(q(categoryData) as never)
})

describe('SpendingPage', () => {
  it('renders the breakdown table with categories ordered highest spend first', () => {
    render(<SpendingPage />)

    const table = screen.getByTestId('breakdown-table')
    const rows = within(table).getAllByRole('row')
    // row[0] is the header.
    const firstData = within(rows[1])
    expect(firstData.getByText('Groceries')).toBeInTheDocument()
    expect(firstData.getByText('$90.00')).toBeInTheDocument()

    // Order: Groceries (90) > Dining (30) > Uncategorized (10).
    const bodyText = rows.slice(1).map((r) => r.textContent ?? '')
    expect(bodyText[0]).toContain('Groceries')
    expect(bodyText[1]).toContain('Dining')
    expect(bodyText[2]).toContain('Uncategorized')
  })

  it('ranks top payees by summed outflow and ignores inflows', () => {
    render(<SpendingPage />)

    const list = screen.getByTestId('top-payees')
    const items = within(list).getAllByRole('listitem')

    // Costco (80) ranks above Netflix (15); Paycheck (inflow) excluded.
    expect(items[0]).toHaveTextContent('Costco')
    expect(items[0]).toHaveTextContent('$80.00')
    expect(items[1]).toHaveTextContent('Netflix')
    expect(within(list).queryByText('Paycheck')).not.toBeInTheDocument()
  })

  it('computes and shows the monthly average', () => {
    render(<SpendingPage />)
    expect(screen.getByTestId('trend-average')).toHaveTextContent('$200.00')
  })

  it('re-calls useSpendingByCategory with the new window when the selector changes', async () => {
    const user = userEvent.setup()
    render(<SpendingPage />)

    // Default window is 1 month.
    expect(mockedSpending).toHaveBeenLastCalledWith(1)

    await user.selectOptions(screen.getByLabelText('Time window'), '6')

    expect(mockedSpending).toHaveBeenLastCalledWith(6)
  })

  it('queries useTransactions with the selected category in the deep-dive', async () => {
    const user = userEvent.setup()
    render(<SpendingPage />)

    // Hidden categories are not offered.
    expect(
      screen.queryByRole('option', { name: /Old Stuff/ }),
    ).not.toBeInTheDocument()

    await user.selectOptions(
      screen.getByLabelText('Deep-dive category'),
      'c1',
    )

    expect(mockedTransactions).toHaveBeenCalledWith({ category_id: 'c1' })
  })

  it('renders empty states without crashing when all data is empty', () => {
    mockedSpending.mockReturnValue(q([]) as never)
    mockedTrend.mockReturnValue(q([]) as never)
    mockedTransactions.mockReturnValue(q([]) as never)
    mockedCategories.mockReturnValue(q([]) as never)

    render(<SpendingPage />)

    expect(
      screen.getByRole('heading', { name: 'Spending Analysis' }),
    ).toBeInTheDocument()
    expect(screen.getByText('No spending in this window yet.')).toBeInTheDocument()
    expect(screen.getByText('No trend data yet.')).toBeInTheDocument()
  })
})
