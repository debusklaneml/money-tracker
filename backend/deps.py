"""FastAPI dependency-injection providers.

Phase 1 (bead bud-ayl): real providers that reuse the existing core classes
under ``src/`` — :class:`~src.cache.database.Database`,
:class:`~src.budget.engine.BudgetEngine` and
:class:`~src.imports.service.ImportService`.

A single shared ``Database`` instance is created lazily on first use and cached
for the lifetime of the process (the FastAPI analogue of the legacy Streamlit
``@st.cache_resource`` wiring in ``app.py``). The engine and import service are
thin wrappers over that one Database, so they are constructed per request — they
hold no state of their own beyond a reference to the shared Database.

Thread-safety: ``Database`` does NOT keep a long-lived connection. Every method
opens a fresh ``sqlite3`` connection via its ``_get_connection`` context manager
and closes it before returning, so the singleton is safe to share across
FastAPI's worker threadpool without ``check_same_thread`` concerns.

Importing this module must stay side-effect free: the Database (and thus the
SQLite file on disk) is only touched when ``get_db`` is first called.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from src.budget.engine import BudgetEngine
from src.cache.database import Database
from src.imports.service import ImportService

# Optional env-var override for the SQLite path (mainly for tests). When unset,
# Database falls back to its own default of ``~/.bud/cache.db``.
_DB_PATH_ENV = "BUD_DB_PATH"


@lru_cache(maxsize=1)
def get_db() -> Database:
    """Provide the shared :class:`Database` singleton.

    Lazily created on first call and cached for the process lifetime, so every
    ``Depends(get_db)`` reuses the same instance. Honours the ``BUD_DB_PATH``
    environment variable when set, otherwise uses the Database default.
    """
    db_path_env = os.environ.get(_DB_PATH_ENV)
    db_path = Path(db_path_env) if db_path_env else None
    return Database(db_path)


def get_engine() -> BudgetEngine:
    """Provide a :class:`BudgetEngine` wired to the shared Database."""
    return BudgetEngine(get_db())


def get_import_service() -> ImportService:
    """Provide an :class:`ImportService` wired to the shared Database."""
    return ImportService(get_db())
