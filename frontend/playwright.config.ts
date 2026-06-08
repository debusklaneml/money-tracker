import { defineConfig, devices } from '@playwright/test'

/**
 * E2E config for the Phase 5 single-process deployment: FastAPI
 * (`backend.main:app`) serves both the built React SPA and the `/api/*`
 * routes on one port. We deliberately test against that real production
 * server (not the Vite dev server) so the SPA fallback for deep links is
 * exercised exactly as it ships.
 *
 * `webServer.command` builds the SPA into `frontend/dist`, then boots the
 * server from the repo root. Playwright waits on `/api/health` before
 * running the specs.
 */
const PORT = process.env.PORT ?? '8000'
const BASE_URL = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    // Build the SPA, then run the real single-process server from the repo
    // root (one level up from this `frontend/` cwd).
    command: `npm run build && cd .. && uv run python -m uvicorn backend.main:app --port ${PORT}`,
    url: `${BASE_URL}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      BUD_NO_BROWSER: '1',
    },
  },
})
