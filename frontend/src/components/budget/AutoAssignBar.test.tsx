import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AutoAssignBar from './AutoAssignBar'

vi.mock('../../lib/queries', () => ({
  useAutoAssign: vi.fn(),
}))

import { useAutoAssign } from '../../lib/queries'

const mockedUseAutoAssign = vi.mocked(useAutoAssign)

let mutate: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  mutate = vi.fn()
  mockedUseAutoAssign.mockReturnValue({
    mutate,
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof useAutoAssign>)
})

describe('AutoAssignBar', () => {
  it('fires the default underfunded strategy for the given month', async () => {
    const user = userEvent.setup()
    render(<AutoAssignBar month="2026-06-01" />)
    await user.click(screen.getByRole('button', { name: /apply/i }))
    expect(mutate).toHaveBeenCalledWith({
      strategy: 'underfunded',
      month: '2026-06-01',
    })
  })

  it('uses the selected strategy', async () => {
    const user = userEvent.setup()
    render(<AutoAssignBar month="2026-06-01" />)
    await user.selectOptions(
      screen.getByRole('combobox', { name: /auto-assign strategy/i }),
      'assigned_last_month',
    )
    await user.click(screen.getByRole('button', { name: /apply/i }))
    expect(mutate).toHaveBeenCalledWith({
      strategy: 'assigned_last_month',
      month: '2026-06-01',
    })
  })

  it('surfaces an error', () => {
    mockedUseAutoAssign.mockReturnValue({
      mutate,
      isPending: false,
      isError: true,
      error: new Error('boom'),
    } as unknown as ReturnType<typeof useAutoAssign>)
    render(<AutoAssignBar />)
    expect(screen.getByRole('alert')).toHaveTextContent('boom')
  })

  it('shows a success message with remaining ready-to-assign', () => {
    mockedUseAutoAssign.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
      isSuccess: true,
      data: { ready_to_assign: 12500 },
    } as unknown as ReturnType<typeof useAutoAssign>)
    render(<AutoAssignBar />)
    // 12500 milliunits → $12.50.
    expect(screen.getByRole('status')).toHaveTextContent(
      'Assigned — $12.50 remaining to assign',
    )
  })
})
