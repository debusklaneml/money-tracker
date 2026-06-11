# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

## Issue Tracking (GitHub-native)

This project tracks work as **GitHub issues** on `debusklaneml/money-tracker`. Shared
state lives server-side — there is no local issue database to sync. Use the global
session commands and the `gh` CLI:

```bash
gh issue list --search "is:open -is:blocked no:assignee"   # the ready set (/next)
gh issue view <issue#> --json title,body,labels            # full context
gh issue edit <issue#> --add-assignee @me                  # claim before touching code (/claim)
```

Conventions:
- **Claim before you touch code:** self-assign the issue and (if a project board exists) move it to `In Progress` before the first commit. An assignee is the "I have this" signal.
- **One branch + one worktree per issue:** branch `<issue#>-<slug>`.
- **Draft PR on first push**, with `Closes #<issue#>` in the body so merging auto-closes the issue.
- **Discovered follow-up work becomes a new issue**, not a TODO comment or markdown list. If a todo needs to survive the session or be seen by someone else, it's an issue.
- Labels: `type:{bug,task,feature,epic}`, `priority:{p0,p1,p2,p3}`, `epic:bud` for this app's epic.
- Durable cross-session knowledge (conventions, gotchas) belongs in this `CLAUDE.md`, not in a standalone `MEMORY.md`/`NOTES.md`.

The repo-wide workflow (Epic issues, sub-issues, native `blocked by` dependencies, the
`/next` · `/claim` · `/plan-ingest` commands) is described in `agentic_dev_workflow.md`.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** — create GitHub issues for anything that needs follow-up
2. **Run quality gates** (if code changed) — tests, linters, builds
3. **Update issue/PR status** — mark the PR ready (`gh pr ready`), move the issue to `In Review`; merging with `Closes #<issue#>` closes it and unblocks dependents
4. **PUSH TO REMOTE** — this is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** — clear stashes, prune merged branches/worktrees
6. **Verify** — all changes committed AND pushed
7. **Hand off** — provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing — that leaves work stranded locally
- NEVER say "ready to push when you are" — YOU must push
- If push fails, resolve and retry until it succeeds

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
  `lru_cache` deps — never `importlib.reload` (a stale editable `.pth` / cached
  module breaks isolation).
- Frontend unit tests live under `frontend/src/`; Playwright E2E lives under
  `frontend/e2e/` (Vitest is scoped to `src/` so the two runners don't collide).
