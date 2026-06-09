import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import EnvelopeGrid from './EnvelopeGrid'

// Mock the data hooks so nothing hits the network.
vi.mock('../../lib/queries', () => ({
  useBudget: vi.fn(),
  useAssign: vi.fn(),
  useSetCategoryTarget: vi.fn(),
  useDeleteCategoryTarget: vi.fn(),
}))

import {
  useBudget,
  useAssign,
  useSetCategoryTarget,
  useDeleteCategoryTarget,
} from '../../lib/queries'

const mockedUseBudget = vi.mocked(useBudget)
const mockedUseAssign = vi.mocked(useAssign)
const mockedUseSetCategoryTarget = vi.mocked(useSetCategoryTarget)
const mockedUseDeleteCategoryTarget = vi.mocked(useDeleteCategoryTarget)

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
let setTargetMutate: ReturnType<typeof vi.fn>
let deleteTargetMutate: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  mutate = vi.fn()
  setTargetMutate = vi.fn()
  deleteTargetMutate = vi.fn()
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
  mockedUseSetCategoryTarget.mockReturnValue({
    mutate: setTargetMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useSetCategoryTarget>)
  mockedUseDeleteCategoryTarget.mockReturnValue({
    mutate: deleteTargetMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useDeleteCategoryTarget>)
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

  it('shows the target amount and an underfunded badge', () => {
    mockedUseBudget.mockReturnValue({
      data: {
        ...sampleBudget,
        categories: [
          {
            id: 'c1',
            group: 'Bills',
            name: 'Rent',
            assigned: 40000,
            activity: 0,
            available: 40000,
            target_amount: 100000,
            target_cadence: 'monthly',
            target_mode: 'refill',
            target_needed: 100000,
            underfunded: 60000,
            is_payment: false,
          },
          {
            id: 'c2',
            group: 'Bills',
            name: 'Power',
            assigned: 30000,
            activity: 0,
            available: 30000,
            target_amount: 30000,
            target_cadence: 'monthly',
            target_mode: 'refill',
            target_needed: 30000,
            underfunded: 0,
            is_payment: false,
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBudget>)
    render(<EnvelopeGrid />)
    // Rent is underfunded by $60.00.
    const badge = screen.getByTestId('underfunded-c1')
    expect(badge).toHaveTextContent('$60.00 underfunded')
    // Power's target is fully funded.
    expect(screen.getByText('Funded ✓')).toBeInTheDocument()
  })

  it('shows "On track" (not "Funded ✓") for a non-monthly target whose envelope is not yet full', () => {
    mockedUseBudget.mockReturnValue({
      data: {
        ...sampleBudget,
        categories: [
          {
            id: 'c1',
            group: 'Bills',
            name: 'Insurance',
            assigned: 0,
            activity: 0,
            available: 10000,
            target_amount: 120000,
            target_cadence: 'yearly',
            target_mode: 'refill',
            target_needed: 120000,
            // Nothing owed this (non-anchor) month, but the envelope is not full.
            underfunded: 0,
            is_payment: false,
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBudget>)
    render(<EnvelopeGrid />)
    expect(screen.getByText('On track')).toBeInTheDocument()
    expect(screen.queryByText('Funded ✓')).not.toBeInTheDocument()
  })

  it('renders a Payment badge for credit-card payment categories', () => {
    mockedUseBudget.mockReturnValue({
      data: {
        ...sampleBudget,
        categories: [
          {
            id: 'cc1',
            group: 'Credit Card Payments',
            name: 'Visa',
            assigned: 0,
            activity: 0,
            available: 0,
            is_payment: true,
          },
          {
            id: 'c2',
            group: 'Bills',
            name: 'Power',
            assigned: 0,
            activity: 0,
            available: 0,
            is_payment: false,
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBudget>)
    render(<EnvelopeGrid />)
    expect(screen.getByTestId('payment-badge-cc1')).toHaveTextContent('Payment')
    expect(screen.queryByTestId('payment-badge-c2')).not.toBeInTheDocument()
  })

  it('opens the target editor, saves a target with correct milliunits/cadence/mode, and clears it', async () => {
    const user = userEvent.setup()
    mockedUseBudget.mockReturnValue({
      data: {
        ...sampleBudget,
        categories: [
          {
            id: 'c1',
            group: 'Bills',
            name: 'Rent',
            assigned: 0,
            activity: 0,
            available: 0,
            target_amount: 50000,
            target_cadence: 'monthly',
            target_mode: 'refill',
            target_needed: 50000,
            underfunded: 0,
            is_payment: false,
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBudget>)
    render(<EnvelopeGrid />)

    // Open the editor.
    await user.click(screen.getByRole('button', { name: /edit target for rent/i }))
    const editor = screen.getByRole('dialog', { name: /edit target for rent/i })

    // Change the amount to $75 and cadence to yearly, mode to full.
    const amountInput = within(editor).getByLabelText(/amount/i)
    await user.clear(amountInput)
    await user.type(amountInput, '75')
    await user.selectOptions(within(editor).getByLabelText(/cadence/i), 'yearly')
    await user.selectOptions(within(editor).getByLabelText(/mode/i), 'full')

    await user.click(within(editor).getByRole('button', { name: /^save$/i }))

    expect(setTargetMutate).toHaveBeenCalledTimes(1)
    expect(setTargetMutate.mock.calls[0][0]).toEqual({
      id: 'c1',
      body: {
        amount_milliunits: 75000,
        cadence: 'yearly',
        mode: 'full',
      },
    })

    // Clear the target.
    await user.click(within(editor).getByRole('button', { name: /clear target/i }))
    expect(deleteTargetMutate).toHaveBeenCalledTimes(1)
    expect(deleteTargetMutate.mock.calls[0][0]).toBe('c1')
  })

  it('includes every_n_months when the custom cadence is chosen', async () => {
    const user = userEvent.setup()
    render(<EnvelopeGrid />)

    // Rent (base sample) has no target → "Set target".
    await user.click(
      screen.getAllByRole('button', { name: /edit target for rent/i })[0],
    )
    const editor = screen.getByRole('dialog', { name: /edit target for rent/i })

    await user.type(within(editor).getByLabelText(/amount/i), '100')
    await user.selectOptions(within(editor).getByLabelText(/cadence/i), 'custom')
    const everyN = within(editor).getByLabelText(/every n months/i)
    await user.clear(everyN)
    await user.type(everyN, '3')
    await user.click(within(editor).getByRole('button', { name: /^save$/i }))

    expect(setTargetMutate.mock.calls[0][0]).toEqual({
      id: 'c1',
      body: {
        amount_milliunits: 100000,
        cadence: 'custom',
        mode: 'refill',
        every_n_months: 3,
      },
    })
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
