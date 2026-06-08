"""FastAPI application entrypoint.

Phase 0 (bead bud-epu): empty/placeholder skeleton only.

This module exposes the FastAPI ``app`` instance, a health check, dev CORS,
and a guarded SPA static-file mount. Real API routers (budget, imports,
transactions, categories, alerts, etc.) are wired up in Phase 1 (bead bud-ayl).
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import (
    accounts,
    alerts,
    budget,
    categories,
    imports,
    insights,
    rules,
    settings,
    transactions,
)

app = FastAPI(title="bud API")

# Dev CORS: allow the Vite dev server to call the API during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# Phase 1 API routers, all mounted under /api.
app.include_router(budget.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

# SPA serving. After the Phase 5 frontend build produces ``frontend/dist``,
# FastAPI serves the compiled single-page app from the same process/port as the
# API. Guarded by an ``is_dir()`` check so it no-ops until the build exists
# (e.g. in CI/tests that haven't run ``npm run build``).
#
# Two pieces, registered AFTER all ``/api/*`` routers so the API always wins:
#   1. Hashed build assets are served from ``/assets`` with StaticFiles.
#   2. A catch-all returns ``index.html`` for every other path so client-side
#      (BrowserRouter) deep links like ``/transactions`` survive a hard refresh.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_INDEX_HTML = _FRONTEND_DIST / "index.html"
# Require index.html, not just the directory: a partial/corrupt build (dir
# present but no index.html) would otherwise 500 on every page load via the
# catch-all. Treat that as "no SPA built" and no-op instead.
if _INDEX_HTML.is_file():
    _ASSETS_DIR = _FRONTEND_DIST / "assets"
    if _ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve the SPA: real root-level files if present, else index.html.

        Unknown ``/api/*`` paths must 404 as JSON rather than silently
        returning the HTML shell, so guard against them explicitly.
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        # Serve genuine root-level static files (favicon, manifest, robots.txt…).
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file() and _FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(_INDEX_HTML)
