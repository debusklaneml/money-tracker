import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import TransactionsPage from '../../routes/TransactionsPage'

vi.mock('../../lib/queries', () => ({
  useTransactions: vi.fn(),
  useAccounts: vi.fn(),
  useCategories: vi.fn(),
  useBulkCategorize: vi.fn(),
  useCategorizeTransaction: vi.fn(),
}))

import {
  useTransactions,
  useAccounts,
  useCategories,
  useBulkCategorize,
  useCategorizeTransaction,
} from '../../lib/queries'

const mockedUseTransactions = vi.mocked(useTransactions)
const mockedUseAccounts = vi.mocked(useAccounts)
const mockedUseCategories = vi.mocked(useCategories)
const mockedUseBulkCategorize = vi.mocked(useBulkCategorize)
const mockedUseCategorizeTransaction = vi.mocked(useCategorizeTransaction)

const sampleTransactions = [
  {
    id: 't1',
    account_id: 'a1',
    account_name: 'Checking',
    date: '2026-06-01',
    amount: -45000, // outflow → -$45.00
    memo: 'Groceries run',
    cleared: 'cleared',
    approved: true,
    flag_color: null,
    payee_id: null,
    payee_name: 'Whole Foods',
    category_id: null, // uncategorized
    category_name: null,
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
  },
  {
    id: 't2',
    account_id: 'a1',
    account_name: 'Checking',
    date: '2026-06-02',
    amount: 250000, // inflow → +$250.00
    memo: null,
    cleared: 'cleared',
    approved: true,
    flag_color: null,
    payee_id: null,
    payee_name: 'Paycheck',
    category_id: 'cat1',
    category_name: 'Income',
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
  },
  {
    id: 't3',
    account_id: 'a2',
    account_name: 'Savings',
    date: '2026-06-03',
    amount: -12000,
    memo: 'Coffee',
    cleared: 'uncleared',
    approved: true,
    flag_color: null,
    payee_id: null,
    payee_name: 'Blue Bottle',
    category_id: null,
    category_name: null,
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
  },
]

const sampleCategories = [
  {
    id: 'cat1',
    category_group_id: 'g1',
    category_group_name: 'Income',
    name: 'Income',
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
    id: 'cat2',
    category_group_id: 'g2',
    category_group_name: 'Everyday',
    name: 'Groceries',
    hidden: false,
    budgeted: 0,
    activity: 0,
    balance: 0,
    goal_type: null,
    goal_target: null,
    goal_target_month: null,
    sort_order: 1,
  },
]

let bulkMutate: ReturnType<typeof vi.fn>
let rowMutate: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  bulkMutate = vi.fn()
  rowMutate = vi.fn()

  mockedUseTransactions.mockReturnValue({
    data: sampleTransactions,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useTransactions>)
  mockedUseAccounts.mockReturnValue({
    data: [
      { id: 'a1', name: 'Checking' },
      { id: 'a2', name: 'Savings' },
    ],
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useAccounts>)
  mockedUseCategories.mockReturnValue({
    data: sampleCategories,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCategories>)
  mockedUseBulkCategorize.mockReturnValue({
    mutate: bulkMutate,
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
  } as unknown as ReturnType<typeof useBulkCategorize>)
  mockedUseCategorizeTransaction.mockReturnValue({
    mutate: rowMutate,
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
  } as unknown as ReturnType<typeof useCategorizeTransaction>)
})

describe('TransactionsPage', () => {
  it('renders transaction rows with payees and a red-styled outflow amount', () => {
    render(<TransactionsPage />)

    expect(screen.getByText('Whole Foods')).toBeInTheDocument()
    expect(screen.getByText('Paycheck')).toBeInTheDocument()
    expect(screen.getByText('Blue Bottle')).toBeInTheDocument()

    const outflow = screen.getByText('-$45.00')
    expect(outflow).toHaveAttribute('data-negative', 'true')
    expect(outflow.className).toContain('rose')
  })

  it('shows the bulk bar with the right count and applies a category to selected rows', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />)

    // No bar until something is selected.
    expect(
      screen.queryByRole('button', { name: /Apply to/ }),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('checkbox', { name: 'Select transaction t1' }),
    )
    await user.click(
      screen.getByRole('checkbox', { name: 'Select transaction t3' }),
    )

    // Count reflects the two selected rows.
    expect(screen.getByText('2 selected')).toBeInTheDocument()
    const applyButton = screen.getByRole('button', { name: 'Apply to 2' })

    // Pick a bulk category and apply.
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Bulk category' }),
      'cat2',
    )
    await user.click(applyButton)

    expect(bulkMutate).toHaveBeenCalledTimes(1)
    expect(bulkMutate).toHaveBeenCalledWith({
      transaction_ids: ['t1', 't3'],
      category_id: 'cat2',
      category_name: 'Groceries',
    })

    // Selection is cleared after applying.
    expect(screen.queryByText('2 selected')).not.toBeInTheDocument()
  })

  it('toggling "Uncategorized only" updates the params passed to useTransactions', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />)

    await user.click(
      screen.getByRole('checkbox', { name: /uncategorized only/i }),
    )

    const lastParams =
      mockedUseTransactions.mock.calls[
        mockedUseTransactions.mock.calls.length - 1
      ][0]
    expect(lastParams).toEqual({ uncategorized: true })
  })

  it('select-all header checkbox selects every row', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />)

    await user.click(
      screen.getByRole('checkbox', { name: 'Select all transactions' }),
    )

    expect(screen.getByText('3 selected')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Apply to 3' }),
    ).toBeInTheDocument()

    // Each row checkbox is now checked.
    for (const id of ['t1', 't2', 't3']) {
      expect(
        screen.getByRole('checkbox', { name: `Select transaction ${id}` }),
      ).toBeChecked()
    }
  })

  it('debounces search before changing the query params', () => {
    vi.useFakeTimers()
    try {
      render(<TransactionsPage />)
      const input = screen.getByRole('searchbox', {
        name: 'Search transactions',
      })

      fireEvent.change(input, { target: { value: 'coff' } })

      // Before the 250ms debounce elapses, params must NOT include the search.
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(
        mockedUseTransactions.mock.calls[
          mockedUseTransactions.mock.calls.length - 1
        ][0],
      ).toEqual({})

      // After the debounce window, the search propagates into the params.
      act(() => {
        vi.advanceTimersByTime(100)
      })
      expect(
        mockedUseTransactions.mock.calls[
          mockedUseTransactions.mock.calls.length - 1
        ][0],
      ).toEqual({ search: 'coff' })
    } finally {
      vi.useRealTimers()
    }
  })

  it('prunes the selection when a selected row leaves the result set', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<TransactionsPage />)

    await user.click(
      screen.getByRole('checkbox', { name: 'Select transaction t1' }),
    )
    await user.click(
      screen.getByRole('checkbox', { name: 'Select transaction t3' }),
    )
    expect(screen.getByText('2 selected')).toBeInTheDocument()

    // t3 disappears (e.g. a refetch after a filter/mutation returns fewer rows).
    mockedUseTransactions.mockReturnValue({
      data: [sampleTransactions[0], sampleTransactions[1]], // t1, t2 only
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTransactions>)
    rerender(<TransactionsPage />)

    // The ghost t3 is pruned; only t1 remains selected.
    expect(screen.getByText('1 selected')).toBeInTheDocument()
  })

  it('resetting a row category to "—" categorizes it as null', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />)

    // t2 is currently categorized (Income); reset it to the blank option.
    const rowSelect = screen.getByRole('combobox', {
      name: 'Category for transaction t2',
    })
    await user.selectOptions(rowSelect, '')

    expect(rowMutate).toHaveBeenCalledWith({
      id: 't2',
      body: { category_id: null, category_name: null },
    })
  })

  it('a per-row category change calls useCategorizeTransaction with id + body', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />)

    const rowSelect = screen.getByRole('combobox', {
      name: 'Category for transaction t1',
    })
    await user.selectOptions(rowSelect, 'cat2')

    expect(rowMutate).toHaveBeenCalledTimes(1)
    expect(rowMutate).toHaveBeenCalledWith({
      id: 't1',
      body: { category_id: 'cat2', category_name: 'Groceries' },
    })
  })

  it('highlights uncategorized rows', () => {
    render(<TransactionsPage />)
    const table = screen.getByTestId('transaction-table')
    const uncategorizedRows = within(table)
      .getAllByRole('row')
      .filter((r) => r.getAttribute('data-uncategorized') === 'true')
    // t1 and t3 are uncategorized.
    expect(uncategorizedRows).toHaveLength(2)
  })
})
