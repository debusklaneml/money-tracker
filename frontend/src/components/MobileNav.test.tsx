import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import AppShell from './AppShell'

// Same data-hook mocks as the AppShell test: render the shell deterministically
// without a real network/fetch.
vi.mock('../lib/queries', () => ({
  useBudget: () => ({ data: { ready_to_assign: 123450 } }),
  useUncategorizedCount: () => ({ data: 3 }),
}))

const SECTIONS = [
  'Budget',
  'Transactions',
  'Import',
  'Categories',
  'Dashboard',
  'Spending',
  'Alerts',
  'Rules',
  'Settings',
] as const

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<div>home page</div>} />
            <Route path="transactions" element={<div>transactions page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MobileNav', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('hides the mobile nav drawer until the hamburger is tapped', () => {
    renderShell()
    // The drawer dialog is not rendered before opening.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    // The hamburger button exists.
    expect(
      screen.getByRole('button', { name: /open navigation menu/i }),
    ).toBeInTheDocument()
  })

  it('reveals every top-level route in the drawer when opened', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(
      screen.getByRole('button', { name: /open navigation menu/i }),
    )

    const drawer = screen.getByRole('dialog', { name: /main navigation/i })
    for (const label of SECTIONS) {
      // Scope to the drawer so we don't collide with the desktop sidebar copy.
      expect(within(drawer).getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('closes the drawer when a nav link is tapped (on navigation)', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(
      screen.getByRole('button', { name: /open navigation menu/i }),
    )
    const drawer = screen.getByRole('dialog', { name: /main navigation/i })

    await user.click(within(drawer).getByRole('link', { name: 'Transactions' }))

    // Navigated to the transactions route...
    expect(screen.getByText('transactions page')).toBeInTheDocument()
    // ...and the drawer is dismissed.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes the drawer on backdrop click and Escape', async () => {
    const user = userEvent.setup()
    renderShell()

    // Backdrop click.
    await user.click(
      screen.getByRole('button', { name: /open navigation menu/i }),
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    // The backdrop is the first "Close navigation menu" affordance.
    const closeButtons = screen.getAllByRole('button', {
      name: /close navigation menu/i,
    })
    await user.click(closeButtons[0])
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // Escape key.
    await user.click(
      screen.getByRole('button', { name: /open navigation menu/i }),
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
