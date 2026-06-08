import { defineConfig, devices } from '@playwright/test'
import os from 'node:os'
import path from 'node:path'

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
 *
 * DB isolation: each run points the backend at a throwaway SQLite file via
 * `BUD_DB_PATH`, so the data-driven happy-path spec starts from a clean,
 * fully-seeded budget (default categories, no transactions) and never touches
 * the developer's real `~/.bud/cache.db`. We also force a fresh server per run
 * (`reuseExistingServer: false`) and a dedicated port so the clean DB is
 * actually the one under test and we don't collide with a dev server on :8000.
 */
const PORT = process.env.PORT ?? '8137'
const BASE_URL = `http://127.0.0.1:${PORT}`

// A unique throwaway DB per run keeps data-driven assertions deterministic.
const E2E_DB_PATH =
  process.env.BUD_DB_PATH ?? path.join(os.tmpdir(), `bud-e2e-${Date.now()}.db`)

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
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      BUD_NO_BROWSER: '1',
      BUD_DB_PATH: E2E_DB_PATH,
    },
  },
})
