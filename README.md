# BUD — Local-First Budgeting

A zero-based budgeting app in the spirit of "give every dollar a job." You
import your bank statements (OFX/QFX), categorize transactions, and assign every
dollar to a category. **No bank connection, no YNAB, no third parties** — all
data lives in a local SQLite database on your machine.

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

## Quick Start

```bash
uv sync
uv run streamlit run app.py
```

Then open the **Import** page and upload an OFX or QFX export from your bank
(look for *Download → Quicken (.qfx)* or *Microsoft Money (.ofx)*).

## Development

BUD's UI is migrating from Streamlit to a React SPA backed by a thin FastAPI
service. During the migration all three run side by side; **Streamlit stays
fully runnable until the migration's final phase.**

Run the backend and frontend dev servers in two terminals:

```bash
# Terminal 1 — FastAPI API on :8000 (auto-reload)
uv run uvicorn backend.main:app --reload

# Terminal 2 — Vite dev server on :5173 (proxies /api → :8000)
cd frontend && npm install && npm run dev
```

Then open http://localhost:5173. The legacy Streamlit app remains available
with `uv run streamlit run app.py` (see Quick Start).

> **Note:** if `uv` is not installed, use the project virtualenv directly:
> `.venv/bin/python -m uvicorn backend.main:app --reload` and
> `.venv/bin/python -m pytest`.

## How the budgeting math works

All money is tracked in milliunits (1/1000 of a dollar) to avoid float errors.

- **Income** = uncategorized inflows (money entering the budget).
- **Assigning** moves money from Ready to Assign into a category for a month.
- **Activity** = the signed sum of a category's categorized transactions.
- **Available** = Σ(assigned + activity) for a category across all months to
  date — so unspent money rolls forward.
- **Ready to Assign** = Σ(all income) − Σ(all assigned). Spending does *not*
  reduce Ready to Assign; it reduces a category's Available.

## Data Privacy

- All data is stored locally in SQLite (`~/.bud/cache.db`).
- Nothing is uploaded anywhere; there is no network/bank integration.

## Project Structure

```
bud/
├── app.py                  # Entry point + navigation + sidebar
├── pages/                  # Budget, Import, Transactions, Categories, Insights
├── src/
│   ├── imports/            # OFX/QFX parser + import service
│   ├── budget/             # The budgeting engine (RTA, rollover, available)
│   ├── cache/              # SQLite database
│   ├── alerts/             # Alert detection algorithms
│   └── utils/              # Formatters, config
└── tests/                  # Engine + import test suite
```

## Tests

```bash
uv run pytest
```

## License

MIT
