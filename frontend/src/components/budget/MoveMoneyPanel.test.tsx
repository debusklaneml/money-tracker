import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import MoveMoneyPanel from './MoveMoneyPanel'

// Mock both data hooks so nothing hits the network.
vi.mock('../../lib/queries', () => ({
  useBudget: vi.fn(),
  useMove: vi.fn(),
}))

import { useBudget, useMove } from '../../lib/queries'

const mockedUseBudget = vi.mocked(useBudget)
const mockedUseMove = vi.mocked(useMove)

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
      activity: 0,
      available: 100000,
    },
    {
      id: 'c2',
      group: 'Bills',
      name: 'Power',
      assigned: 0,
      activity: -2000,
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
  mockedUseMove.mockReturnValue({
    mutate,
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
  } as unknown as ReturnType<typeof useMove>)
})

describe('MoveMoneyPanel', () => {
  it('renders nothing when open=false', () => {
    render(<MoveMoneyPanel open={false} onClose={vi.fn()} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('renders the dialog with From/To selects populated with both categories', () => {
    render(<MoveMoneyPanel open onClose={vi.fn()} />)

    expect(screen.getByRole('dialog')).toBeTruthy()

    const from = screen.getByLabelText('Move from') as HTMLSelectElement
    const to = screen.getByLabelText('Move to') as HTMLSelectElement

    // Each select has a placeholder option plus both categories.
    expect(within(from).queryByText('Bills › Rent')).toBeTruthy()
    expect(within(from).queryByText('Bills › Power')).toBeTruthy()
    expect(within(to).queryByText('Bills › Rent')).toBeTruthy()
    expect(within(to).queryByText('Bills › Power')).toBeTruthy()
  })

  it('performs a valid move and closes', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<MoveMoneyPanel open onClose={onClose} month="2026-06-01" />)

    await user.selectOptions(screen.getByLabelText('Move from'), 'c1')
    await user.selectOptions(screen.getByLabelText('Move to'), 'c2')
    await user.type(screen.getByLabelText('Amount to move'), '20')

    await user.click(screen.getByRole('button', { name: 'Move' }))

    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate).toHaveBeenCalledWith({
      from_id: 'c1',
      to_id: 'c2',
      amount: 20000,
      month: '2026-06-01',
    })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('passes month: null when no month prop is given', async () => {
    const user = userEvent.setup()
    render(<MoveMoneyPanel open onClose={vi.fn()} />)

    await user.selectOptions(screen.getByLabelText('Move from'), 'c1')
    await user.selectOptions(screen.getByLabelText('Move to'), 'c2')
    await user.type(screen.getByLabelText('Amount to move'), '5')
    await user.click(screen.getByRole('button', { name: 'Move' }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ month: null }),
    )
  })

  it('does not move when From === To', async () => {
    const user = userEvent.setup()
    render(<MoveMoneyPanel open onClose={vi.fn()} />)

    await user.selectOptions(screen.getByLabelText('Move from'), 'c1')
    await user.selectOptions(screen.getByLabelText('Move to'), 'c1')
    await user.type(screen.getByLabelText('Amount to move'), '20')

    const moveBtn = screen.getByRole('button', { name: 'Move' })
    expect((moveBtn as HTMLButtonElement).disabled).toBe(true)

    await user.click(moveBtn)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('does not move when amount is invalid', async () => {
    const user = userEvent.setup()
    render(<MoveMoneyPanel open onClose={vi.fn()} />)

    await user.selectOptions(screen.getByLabelText('Move from'), 'c1')
    await user.selectOptions(screen.getByLabelText('Move to'), 'c2')
    await user.type(screen.getByLabelText('Amount to move'), 'abc')

    const moveBtn = screen.getByRole('button', { name: 'Move' })
    expect((moveBtn as HTMLButtonElement).disabled).toBe(true)

    await user.click(moveBtn)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('preselects From/To from defaults', () => {
    render(
      <MoveMoneyPanel
        open
        onClose={vi.fn()}
        defaultFromId="c1"
        defaultToId="c2"
      />,
    )

    expect((screen.getByLabelText('Move from') as HTMLSelectElement).value).toBe(
      'c1',
    )
    expect((screen.getByLabelText('Move to') as HTMLSelectElement).value).toBe(
      'c2',
    )
  })

  it('cover overspending fills the amount with the destination shortfall', async () => {
    const user = userEvent.setup()
    render(<MoveMoneyPanel open onClose={vi.fn()} defaultToId="c2" />)

    // c2 has available -2000 (=> needs $2.00 to cover).
    expect(screen.getByText(/needs/i)).toBeTruthy()

    await user.click(
      screen.getByRole('button', { name: 'Cover overspending' }),
    )

    await user.selectOptions(screen.getByLabelText('Move from'), 'c1')
    await user.click(screen.getByRole('button', { name: 'Move' }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ from_id: 'c1', to_id: 'c2', amount: 2000 }),
    )
  })
})
