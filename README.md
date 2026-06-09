# BUD — Local-First Budgeting

A zero-based budgeting app in the spirit of "give every dollar a job." You
import your bank statements (OFX/QFX), categorize transactions, and assign every
dollar to a category. **No bank connection, no YNAB, no third parties** — all
data lives in a local SQLite database on your machine.

BUD is a single-user, local-first desktop-style web app: a React single-page
app served by a small FastAPI backend, both running on one local port.

## Features

- **Budget** — Ready to Assign front and center; assign every dollar to an
  envelope, move money to cover overspending. Balances roll over month to month.
- **Import** — Upload OFX/QFX statements. Transactions are deduplicated by the
  bank's FITID, so re-importing an overlapping statement never doubles up.
- **Transactions** — Categorize transactions and build auto-rules
  (payee/memo → category) that apply on every future import.
- **Categories** — Create, rename, regroup, and remove your envelopes. Ships
  with sensible defaults you can edit.
- **Insights** — Dashboard, spending analysis, and statistical alerts
  (Modified Z-Score unusual-spending detection).

## Architecture

BUD is three layers:

- **Frontend** (`frontend/`) — a React + TypeScript single-page app built with
  Vite. Routing is client-side (React Router); data fetching uses TanStack
  Query; tables and charts use TanStack Table and Recharts.
- **Backend** (`backend/`) — a thin FastAPI service. Routers live under
  `backend/routers/` and are all mounted under `/api/*` (budget, categories,
  transactions, imports, rules, accounts, insights, alerts, settings). A
  liveness probe lives at `GET /api/health` → `{"status": "ok"}`.
- **Core** (`src/`) — the unchanged Python domain logic the API wraps: the
  budgeting engine, the OFX/QFX import service, the SQLite cache, and the
  alert-detection algorithms.

**Single-process serving.** In normal use there is just one server on one port.
FastAPI serves the compiled SPA from `frontend/dist` *and* the JSON API from the
same process. API routes are matched first; everything else falls back to the
SPA's `index.html`, so client-side deep links (e.g. `/transactions`) survive a
hard refresh. The static mount is guarded by an `is_dir()` check, so the API
still runs in tests/CI even when no frontend build is present.

> BUD's UI was migrated from Streamlit to this React + FastAPI stack; the Python
> core in `src/` was carried over unchanged.

## Getting Started

You need [`uv`](https://github.com/astral-sh/uv) for the Python side and
[Node.js](https://nodejs.org/) (with `npm`) for the frontend.

### Production / normal use (single command)

Build the frontend once, then run the app from the repo root. This starts the
server on `http://127.0.0.1:8000` and opens your browser automatically.

```bash
# 1. Build the SPA (only needed once, or whenever the frontend changes)
cd frontend
npm install
npm run build
cd ..

# 2. Install Python deps and launch
uv sync
uv run bud
```

`uv run bud` is equivalent to:

```bash
uv run python -m backend.launch
```

Environment variables:

- `BUD_HOST` — interface to bind to (default `127.0.0.1`, loopback only).
  Set `BUD_HOST=0.0.0.0` to bind all interfaces and reach BUD from other
  devices on your LAN. **⚠️ BUD has no authentication.** Only expose it on a
  trusted network or behind a reverse proxy that handles auth/TLS.
- `BUD_PORT` — serve on a port other than `8000`.
- `BUD_NO_BROWSER=1` — start the server without opening a browser.

### Development (hot reload, two processes)

For UI work you typically run the backend and the Vite dev server side by side.
The Vite server proxies `/api` to the backend, so the SPA can call the API
without CORS friction.

```bash
# Terminal 1 — FastAPI API on :8000 (auto-reload)
uv run python -m uvicorn backend.main:app --reload --port 8000
```

```bash
# Terminal 2 — Vite dev server on :5173 (proxies /api → :8000)
cd frontend
npm install
npm run dev
```

Then open <http://localhost:5173>.

After importing data, head to the **Import** page and upload an OFX or QFX
export from your bank (look for *Download → Quicken (.qfx)* or
*Microsoft Money (.ofx)*).

## How the budgeting math works

All money is tracked in milliunits (1/1000 of a dollar) to avoid float errors.

- **Income** = uncategorized inflows (money entering the budget).
- **Assigning** moves money from Ready to Assign into a category for a month.
- **Activity** = the signed sum of a category's categorized transactions.
- **Available** = Σ(assigned + activity) for a category across all months to
  date — so unspent money rolls forward.
- **Ready to Assign** = Σ(all income) − Σ(all assigned). Spending does *not*
  reduce Ready to Assign; it reduces a category's Available.

## Development

### Project layout

```
bud/
├── backend/                # FastAPI app
│   ├── main.py             # App instance, /api/health, routers, SPA serving
│   ├── routers/            # /api/* endpoints (budget, imports, …)
│   ├── schemas.py          # Pydantic request/response models
│   └── deps.py             # Shared dependencies
├── frontend/               # React + TypeScript SPA (Vite)
│   ├── src/                # Components, pages, hooks
│   └── dist/               # Production build (served by the backend)
├── src/                    # Python core (unchanged domain logic)
│   ├── imports/            # OFX/QFX parser + import service
│   ├── budget/             # Budgeting engine (RTA, rollover, available)
│   ├── cache/              # SQLite database
│   ├── alerts/             # Alert detection algorithms
│   └── utils/              # Formatters, config
└── tests/                  # Backend / API test suite
```

### Tests

```bash
# Backend + API (pytest, 39 tests)
uv run python -m pytest

# Frontend unit tests (Vitest)
cd frontend && npm test

# End-to-end browser tests (Playwright)
cd frontend && npm run e2e
```

> If `uv` is not installed, you can use the project virtualenv directly, e.g.
> `.venv/bin/python -m pytest` and
> `.venv/bin/python -m uvicorn backend.main:app --reload`.

## Self-hosting & remote access

Want to run BUD on a home server and reach it from your phone? See:

- **[docs/self-hosting.md](docs/self-hosting.md)** — end-to-end runbook: headless
  run, systemd/launchd service, reverse proxy, iPhone LAN access, and backups.
- **[docs/access-control.md](docs/access-control.md)** — the security posture to
  apply **before** exposing BUD on a network (it has no built-in auth).

## Data & Privacy

- All data is stored locally in SQLite (`~/.bud/cache.db`).
- Nothing is uploaded anywhere; there is no network or bank integration and no
  third-party services.

## License

MIT
