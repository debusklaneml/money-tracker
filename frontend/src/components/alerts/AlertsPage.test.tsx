import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AlertsPage from '../../routes/AlertsPage'
import type { Alert, MessageResponse } from '../../lib/types'

vi.mock('../../lib/queries', () => ({
  useAlerts: vi.fn(),
  useRunAlerts: vi.fn(),
  useDismissAlert: vi.fn(),
  useAcknowledgeAlert: vi.fn(),
}))

import {
  useAlerts,
  useRunAlerts,
  useDismissAlert,
  useAcknowledgeAlert,
} from '../../lib/queries'

const mockedUseAlerts = vi.mocked(useAlerts)
const mockedUseRunAlerts = vi.mocked(useRunAlerts)
const mockedUseDismissAlert = vi.mocked(useDismissAlert)
const mockedUseAcknowledgeAlert = vi.mocked(useAcknowledgeAlert)

function makeAlert(over: Partial<Alert>): Alert {
  return {
    id: 1,
    alert_type: 'overspent',
    severity: 'info',
    title: 'Alert',
    description: null,
    related_entity_id: null,
    related_entity_type: null,
    metadata: null,
    created_at: '2026-06-01T12:00:00Z',
    acknowledged_at: null,
    dismissed: false,
    ...over,
  }
}

// Mixed severities; alert 3 is already acknowledged. Note the array order is
// deliberately NOT severity-sorted so we can assert the page sorts it.
const sampleAlerts: Alert[] = [
  makeAlert({
    id: 1,
    severity: 'info',
    title: 'Info alert',
    description: 'An informational note.',
    created_at: '2026-06-05T09:00:00Z',
  }),
  makeAlert({
    id: 2,
    severity: 'critical',
    title: 'Critical alert',
    description: 'Something is very wrong.',
    created_at: '2026-06-03T09:00:00Z',
  }),
  makeAlert({
    id: 3,
    severity: 'warning',
    title: 'Warning alert',
    description: 'Heads up.',
    created_at: '2026-06-04T09:00:00Z',
    acknowledged_at: '2026-06-04T10:00:00Z',
  }),
]

let runMutate: ReturnType<typeof vi.fn>
let dismissMutate: ReturnType<typeof vi.fn>
let acknowledgeMutate: ReturnType<typeof vi.fn>

function setHooks(
  over: {
    alerts?: Partial<ReturnType<typeof useAlerts>>
    run?: Record<string, unknown>
    dismiss?: Record<string, unknown>
    acknowledge?: Record<string, unknown>
  } = {},
) {
  mockedUseAlerts.mockReturnValue({
    data: sampleAlerts,
    isLoading: false,
    isError: false,
    ...over.alerts,
  } as unknown as ReturnType<typeof useAlerts>)
  mockedUseRunAlerts.mockReturnValue({
    mutate: runMutate,
    mutateAsync: vi.fn().mockResolvedValue({ status: 'ok', message: '' }),
    isPending: false,
    variables: undefined,
    ...over.run,
  } as unknown as ReturnType<typeof useRunAlerts>)
  mockedUseDismissAlert.mockReturnValue({
    mutate: dismissMutate,
    mutateAsync: vi.fn(),
    isPending: false,
    variables: undefined,
    ...over.dismiss,
  } as unknown as ReturnType<typeof useDismissAlert>)
  mockedUseAcknowledgeAlert.mockReturnValue({
    mutate: acknowledgeMutate,
    mutateAsync: vi.fn(),
    isPending: false,
    variables: undefined,
    ...over.acknowledge,
  } as unknown as ReturnType<typeof useAcknowledgeAlert>)
}

beforeEach(() => {
  vi.clearAllMocks()
  runMutate = vi.fn()
  dismissMutate = vi.fn()
  acknowledgeMutate = vi.fn()
  setHooks()
})

describe('AlertsPage', () => {
  it('renders alert titles and severity badges', () => {
    render(<AlertsPage />)

    expect(screen.getByText('Info alert')).toBeInTheDocument()
    expect(screen.getByText('Critical alert')).toBeInTheDocument()
    expect(screen.getByText('Warning alert')).toBeInTheDocument()

    // Severity badge text appears within the critical card.
    const critical = within(screen.getByTestId('alert-card-2'))
    expect(critical.getByText('critical')).toBeInTheDocument()
  })

  it('sorts alerts critical-first, then warning, then info', () => {
    render(<AlertsPage />)

    const cards = screen.getAllByTestId(/^alert-card-/)
    expect(cards.map((c) => c.getAttribute('data-testid'))).toEqual([
      'alert-card-2', // critical
      'alert-card-3', // warning
      'alert-card-1', // info
    ])
  })

  it('shows a severity summary derived from the list', () => {
    render(<AlertsPage />)
    expect(
      screen.getByText('1 critical · 1 warning · 1 info'),
    ).toBeInTheDocument()
  })

  it('runs detection and surfaces the server count message', () => {
    render(<AlertsPage />)

    act(() => {
      screen.getByRole('button', { name: 'Run detection' }).click()
    })
    expect(runMutate).toHaveBeenCalledTimes(1)
    // First arg is `undefined` (no variables), second is the options object.
    expect(runMutate.mock.calls[0][0]).toBeUndefined()

    const opts = runMutate.mock.calls[0][1] as {
      onSuccess: (r: MessageResponse) => void
    }
    act(() =>
      opts.onSuccess({
        status: 'ok',
        message: 'Detected and saved 2 new alert(s).',
      }),
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      'Detected and saved 2 new alert(s).',
    )
  })

  it('surfaces an error when detection fails', () => {
    render(<AlertsPage />)

    act(() => {
      screen.getByRole('button', { name: 'Run detection' }).click()
    })
    const opts = runMutate.mock.calls[0][1] as {
      onError: (e: Error) => void
    }
    act(() => opts.onError(new Error('Detection failed')))

    expect(screen.getByRole('alert')).toHaveTextContent('Detection failed')
  })

  it('shows the running state while detection is pending', () => {
    setHooks({ run: { isPending: true } })
    render(<AlertsPage />)
    expect(
      screen.getByRole('button', { name: 'Running…' }),
    ).toBeInTheDocument()
  })

  it('dismisses an alert with its id', async () => {
    const user = userEvent.setup()
    render(<AlertsPage />)

    await user.click(screen.getByRole('button', { name: 'Dismiss alert 2' }))
    expect(dismissMutate).toHaveBeenCalledWith(2, expect.any(Object))
  })

  it('acknowledges an alert with its id', async () => {
    const user = userEvent.setup()
    render(<AlertsPage />)

    await user.click(
      screen.getByRole('button', { name: 'Acknowledge alert 1' }),
    )
    expect(acknowledgeMutate).toHaveBeenCalledWith(1, expect.any(Object))
  })

  it('does not offer Acknowledge for an already-acknowledged alert', () => {
    render(<AlertsPage />)

    // Alert 3 is acknowledged: it shows the indicator but no Acknowledge button.
    const card = within(screen.getByTestId('alert-card-3'))
    expect(card.getByText('Acknowledged')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Acknowledge alert 3' }),
    ).not.toBeInTheDocument()
    // Dismiss is still available.
    expect(
      screen.getByRole('button', { name: 'Dismiss alert 3' }),
    ).toBeInTheDocument()
  })

  it('disables only the busy card while a mutation is in flight', () => {
    setHooks({ dismiss: { isPending: true, variables: 2 } })
    render(<AlertsPage />)

    expect(
      screen.getByRole('button', { name: 'Dismiss alert 2' }),
    ).toBeDisabled()
    // A different card stays interactive.
    expect(
      screen.getByRole('button', { name: 'Dismiss alert 1' }),
    ).not.toBeDisabled()
  })

  it('shows the loading state', () => {
    setHooks({ alerts: { data: undefined, isLoading: true, isError: false } })
    render(<AlertsPage />)
    expect(screen.getByText(/loading alerts/i)).toBeInTheDocument()
  })

  it('shows the error state', () => {
    setHooks({ alerts: { data: undefined, isLoading: false, isError: true } })
    render(<AlertsPage />)
    expect(screen.getByText(/failed to load alerts/i)).toBeInTheDocument()
  })

  it('shows the empty state when there are no alerts', () => {
    setHooks({ alerts: { data: [], isLoading: false, isError: false } })
    render(<AlertsPage />)
    expect(
      screen.getByText(/no active alerts\. run detection to check/i),
    ).toBeInTheDocument()
  })
})
