import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import AppShell from './AppShell'

// Mock the data hooks so the shell renders deterministically without a real
// network/fetch. The real implementations live in ../lib/queries (written by
// another agent); the shell only depends on the .data shape contract.
vi.mock('../lib/queries', () => ({
  useBudget: () => ({ data: { ready_to_assign: 123450 } }),
  useUncategorizedCount: () => ({ data: 3 }),
}))

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<div>home</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the main navigation with all section links', () => {
    renderShell()
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()
    for (const label of [
      'Budget',
      'Transactions',
      'Import',
      'Categories',
      'Dashboard',
      'Alerts',
      'Rules',
      'Settings',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('renders the BUD brand and Ready to Assign label', () => {
    renderShell()
    expect(screen.getAllByText('BUD').length).toBeGreaterThan(0)
    expect(screen.getByText(/ready to assign/i)).toBeInTheDocument()
  })

  it('renders the uncategorized badge with the count', () => {
    renderShell()
    expect(screen.getByText(/3 uncategorized/i)).toBeInTheDocument()
  })

  it('renders the active route via the outlet', () => {
    renderShell()
    expect(screen.getByText('home')).toBeInTheDocument()
  })
})
