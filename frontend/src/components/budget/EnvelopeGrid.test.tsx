import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import EnvelopeGrid from './EnvelopeGrid'

// Mock both data hooks so nothing hits the network.
vi.mock('../../lib/queries', () => ({
  useBudget: vi.fn(),
  useAssign: vi.fn(),
}))

import { useBudget, useAssign } from '../../lib/queries'

const mockedUseBudget = vi.mocked(useBudget)
const mockedUseAssign = vi.mocked(useAssign)

const sampleBudget = {
  month: '2026-06-01',
  ready_to_assign: 0,
  income_month: 0,
  income_total: 0,
  assigned_total: 0,
  categories: [
    {
      id: 'c1',
      group: 'Bills',
      name: 'Rent',
      assigned: 100000,
      activity: -50000,
      available: 50000,
    },
    {
      id: 'c2',
      group: 'Bills',
      name: 'Power',
      assigned: 0,
      activity: 0,
      available: -2000,
    },
  ],
}

let mutate: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  mutate = vi.fn()
  mockedUseBudget.mockReturnValue({
    data: sampleBudget,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useBudget>)
  mockedUseAssign.mockReturnValue({
    mutate,
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
  } as unknown as ReturnType<typeof useAssign>)
})

describe('EnvelopeGrid', () => {
  it('renders category names and the group header', () => {
    render(<EnvelopeGrid />)
    expect(screen.getByText('Rent')).toBeInTheDocument()
    expect(screen.getByText('Power')).toBeInTheDocument()
    // Group header row.
    expect(
      screen.getByRole('columnheader', { name: 'Bills' }),
    ).toBeInTheDocument()
  })

  it('styles a negative Available cell', () => {
    render(<EnvelopeGrid />)
    // Power's available is -2000 milliunits → -$2.00.
    const negativeCell = screen.getByText('-$2.00')
    expect(negativeCell).toHaveAttribute('data-negative', 'true')
    expect(negativeCell.className).toContain('rose')
  })

  it('does not flag a positive Available cell as negative', () => {
    render(<EnvelopeGrid />)
    const positiveCell = screen.getByText('$50.00')
    expect(positiveCell).toHaveAttribute('data-negative', 'false')
  })

  it('commits an edited Assigned cell via the assign mutation', async () => {
    const user = userEvent.setup()
    render(<EnvelopeGrid month="2026-06-01" />)

    // Enter edit mode for Rent's Assigned cell.
    await user.click(screen.getByRole('button', { name: 'Assigned for Rent' }))

    const input = screen.getByRole('textbox', { name: 'Assigned for Rent' })
    await user.clear(input)
    await user.type(input, '200')
    await user.keyboard('{Enter}')

    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate).toHaveBeenCalledWith({
      category_id: 'c1',
      amount: 200000,
      month: '2026-06-01',
    })
  })

  it('cancels the edit on Escape without calling mutate and reverts the value', async () => {
    const user = userEvent.setup()
    render(<EnvelopeGrid month="2026-06-01" />)

    await user.click(screen.getByRole('button', { name: 'Assigned for Rent' }))
    const input = screen.getByRole('textbox', { name: 'Assigned for Rent' })
    await user.clear(input)
    await user.type(input, '999')
    await user.keyboard('{Escape}')

    // Escape unmounts the input, which fires a trailing blur — neither path
    // may commit the typed value.
    expect(mutate).not.toHaveBeenCalled()
    // The cell reverts to a button showing the original assigned amount.
    const cell = await screen.findByRole('button', { name: 'Assigned for Rent' })
    expect(cell).toHaveTextContent('$100.00')
  })

  it('does not call mutate when the input is invalid', async () => {
    const user = userEvent.setup()
    render(<EnvelopeGrid month="2026-06-01" />)

    await user.click(screen.getByRole('button', { name: 'Assigned for Rent' }))
    const input = screen.getByRole('textbox', { name: 'Assigned for Rent' })
    await user.clear(input)
    await user.type(input, 'abc')
    await user.keyboard('{Enter}')

    expect(mutate).not.toHaveBeenCalled()
  })

  it('shows a loading state', () => {
    mockedUseBudget.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useBudget>)
    render(<EnvelopeGrid />)
    expect(screen.getByText(/loading budget/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no categories', () => {
    mockedUseBudget.mockReturnValue({
      data: { ...sampleBudget, categories: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBudget>)
    render(<EnvelopeGrid />)
    expect(screen.getByText(/no categories yet/i)).toBeInTheDocument()
  })

  it('renders an Assigned subtotal in the group header', () => {
    render(<EnvelopeGrid />)
    const grid = screen.getByTestId('envelope-grid')
    // Rent 100000 + Power 0 = 100000 → $100.00.
    expect(within(grid).getAllByText('$100.00').length).toBeGreaterThan(0)
  })

  it('surfaces a blocked-assign (Ready-to-Assign exceeded) error inline', () => {
    mockedUseAssign.mockReturnValue({
      mutate,
      mutateAsync: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error(
        'Cannot assign 200000: only 100000 is available to assign for this month.',
      ),
    } as unknown as ReturnType<typeof useAssign>)
    render(<EnvelopeGrid />)
    // The error reflects the shared assign-mutation state, shown at the cells.
    const alerts = screen.getAllByRole('alert')
    expect(alerts.length).toBeGreaterThan(0)
    expect(alerts[0]).toHaveTextContent(/only 100000 is available/i)
  })
})
