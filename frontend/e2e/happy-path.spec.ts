import { test, expect } from '@playwright/test'

/**
 * Phase 5 happy-path smoke test against the single-process FastAPI server
 * that serves both the built React SPA and `/api/*` on one port.
 *
 * The most important assertion here is the deep-link reload: navigating
 * directly to a client-side route must still render the SPA, which proves
 * FastAPI's catch-all fallback to `index.html` is wired up correctly.
 */

test('app shell loads with navigation', async ({ page }) => {
  await page.goto('/')

  // Main nav landmark from AppShell (`aria-label="Main navigation"`).
  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  await expect(nav).toBeVisible()

  // The index route renders the Budget page heading.
  await expect(page.getByRole('heading', { name: 'Budget' })).toBeVisible()
})

test('navigation between routes works', async ({ page }) => {
  await page.goto('/')

  const nav = page.getByRole('navigation', { name: 'Main navigation' })

  // Click through to Transactions and assert its heading renders.
  await nav.getByRole('link', { name: 'Transactions' }).click()
  await expect(page).toHaveURL(/\/transactions$/)
  await expect(
    page.getByRole('heading', { name: 'Transactions' }),
  ).toBeVisible()

  // Click through to an Insights page (Spending) and assert its heading.
  await nav.getByRole('link', { name: 'Spending' }).click()
  await expect(page).toHaveURL(/\/spending$/)
  await expect(
    page.getByRole('heading', { name: 'Spending Analysis' }),
  ).toBeVisible()
})

test('deep-link reload survives (SPA fallback)', async ({ page }) => {
  // Navigate DIRECTLY to a client-side route (not via an in-app click). A
  // full HTTP GET for /transactions must be served the SPA by FastAPI and
  // then client-side routed to the Transactions page.
  await page.goto('/transactions')

  await expect(
    page.getByRole('heading', { name: 'Transactions' }),
  ).toBeVisible()

  // Nav shell is present too, confirming the full app booted, not an error page.
  await expect(
    page.getByRole('navigation', { name: 'Main navigation' }),
  ).toBeVisible()
})
