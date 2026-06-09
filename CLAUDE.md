# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Build & Test

Python env is managed with **uv**; the frontend with **npm** (in `frontend/`).

```bash
# One-time setup
uv sync                                   # Python deps + editable install
cd frontend && npm install && npm run build && cd ..

# Run the whole app (one process, opens browser at http://127.0.0.1:8000)
uv run bud                                # == uv run python -m backend.launch
# env overrides: BUD_HOST (default 127.0.0.1), BUD_PORT (default 8000), BUD_NO_BROWSER=1
# BUD_HOST=0.0.0.0 binds all interfaces / exposes on the LAN — BUD has NO auth,
# so only do that on a trusted network or behind an auth/TLS reverse proxy.

# Dev mode (hot reload, two processes)
uv run python -m uvicorn backend.main:app --reload --port 8000   # terminal 1
cd frontend && npm run dev                                        # terminal 2 (Vite :5173, proxies /api)

# Tests
uv run python -m pytest                   # backend (pytest)
cd frontend && npm test                   # frontend unit (Vitest)
cd frontend && npm run e2e                # E2E (Playwright, boots the real server)
```

If `import backend` ever fails after switching install modes, the fix is
`rm -rf .venv && uv sync` (a stale editable `.pth` can linger).

## Architecture Overview

A React + TypeScript SPA (`frontend/`, Vite) talks to a thin **FastAPI** backend
(`backend/`, routers under `/api/*`) that wraps the Python core in `src/` (budget
engine, OFX import service, SQLite cache, alerts). In production FastAPI serves
the built SPA (`frontend/dist`) **and** the API on one port, with a catch-all that
returns `index.html` so client-side deep links survive a refresh. Local,
single-user, no auth; all data in a local SQLite DB. (Migrated from Streamlit in
Phase 5.)

## Conventions & Patterns

- **Money is stored in milliunits** (integer thousandths of a dollar) end to end;
  format only at the display edge.
- Backend router tests isolate the DB via `BUD_DB_PATH` + `cache_clear()` on the
  `lru_cache` deps — never `importlib.reload` (see the beads memory on test isolation).
- Frontend unit tests live under `frontend/src/`; Playwright E2E lives under
  `frontend/e2e/` (Vitest is scoped to `src/` so the two runners don't collide).
