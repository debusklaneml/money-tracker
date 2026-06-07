"""FastAPI application entrypoint.

Phase 0 (bead bud-epu): empty/placeholder skeleton only.

This module exposes the FastAPI ``app`` instance, a health check, dev CORS,
and a guarded SPA static-file mount. Real API routers (budget, imports,
transactions, categories, alerts, etc.) are wired up in Phase 1 (bead bud-ayl).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import budget, categories, imports, transactions

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

# Placeholder SPA mount. After the Phase 5 frontend build produces
# ``frontend/dist``, this serves the compiled single-page app. It is mounted
# LAST so that ``/api/*`` routes always take precedence over the catch-all,
# and guarded by an ``is_dir()`` check so it no-ops until the build exists.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="spa")
