import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

import type { BudgetState } from '../../lib/types'
import ReadyToAssignHeader from './ReadyToAssignHeader'

vi.mock('../../lib/queries', () => ({ useBudget: vi.fn() }))
import { useBudget } from '../../lib/queries'

const mockUseBudget = vi.mocked(useBudget)

function makeBudget(overrides: Partial<BudgetState> = {}): BudgetState {
  return {
    month: '2026-06-01',
    ready_to_assign: 0,
    income_month: 0,
    income_total: 0,
    assigned_total: 0,
    categories: [],
    ...overrides,
  }
}

function mockState(value: ReturnType<typeof mockUseBudget>) {
  // The component only reads data/isLoading/isError; cast keeps the test terse.
  mockUseBudget.mockReturnValue(value as never)
}

beforeEach(() => {
  mockUseBudget.mockReset()
})

describe('ReadyToAssignHeader', () => {
  it('shows the emerald "Ready to Assign" state for a positive RTA', () => {
    mockState({
      data: makeBudget({
        ready_to_assign: 1_234_560,
        income_month: 5_000_000,
        assigned_total: 3_765_440,
      }),
      isLoading: false,
      isError: false,
    } as never)

    render(<ReadyToAssignHeader />)

    const container = screen.getByRole('status')
    expect(container).toHaveAttribute('data-state', 'to-assign')
    expect(screen.getByText('Ready to Assign')).toBeInTheDocument()

    const amount = screen.getByTestId('rta-amount')
    expect(amount).toHaveTextContent('$1,234.56')
    expect(amount.className).toContain('text-emerald-600')

    // Secondary figures rendered.
    expect(screen.getByText('$5,000.00')).toBeInTheDocument()
    expect(screen.getByText('$3,765.44')).toBeInTheDocument()
    // Month label.
    expect(screen.getByText('June 2026')).toBeInTheDocument()
  })

  it('shows the over-assigned (rose) state for a negative RTA', () => {
    mockState({
      data: makeBudget({ ready_to_assign: -50_000 }),
      isLoading: false,
      isError: false,
    } as never)

    render(<ReadyToAssignHeader />)

    const container = screen.getByRole('status')
    expect(container).toHaveAttribute('data-state', 'over-assigned')
    expect(screen.getByText('Over-assigned')).toBeInTheDocument()

    const amount = screen.getByTestId('rta-amount')
    expect(amount).toHaveTextContent('-$50.00')
    expect(amount.className).toContain('text-rose-600')
  })

  it('shows the balanced (slate) state when RTA is exactly zero', () => {
    mockState({
      data: makeBudget({ ready_to_assign: 0 }),
      isLoading: false,
      isError: false,
    } as never)

    render(<ReadyToAssignHeader />)

    const container = screen.getByRole('status')
    expect(container).toHaveAttribute('data-state', 'all-assigned')
    expect(screen.getByText('All money assigned')).toBeInTheDocument()

    const amount = screen.getByTestId('rta-amount')
    expect(amount).toHaveTextContent('$0.00')
    expect(amount.className).toContain('text-slate-700')
  })

  it('renders a skeleton (no amount) while loading', () => {
    mockState({
      data: undefined,
      isLoading: true,
      isError: false,
    } as never)

    render(<ReadyToAssignHeader />)

    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByTestId('rta-amount')).not.toBeInTheDocument()
  })

  it('renders an inline error note on error', () => {
    mockState({
      data: undefined,
      isLoading: false,
      isError: true,
    } as never)

    render(<ReadyToAssignHeader />)

    expect(screen.getByRole('status')).toHaveTextContent(/load the budget/i)
    expect(screen.queryByTestId('rta-amount')).not.toBeInTheDocument()
  })

  it('forwards the month prop to useBudget', () => {
    mockState({
      data: makeBudget({ month: '2026-03-01', ready_to_assign: 100 }),
      isLoading: false,
      isError: false,
    } as never)

    render(<ReadyToAssignHeader month="2026-03-01" />)

    expect(mockUseBudget).toHaveBeenCalledWith('2026-03-01')
    expect(screen.getByText('March 2026')).toBeInTheDocument()
  })
})
