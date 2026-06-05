"""FastAPI dependency-injection providers (PLACEHOLDER).

Phase 0 (bead bud-epu): these are stubs only. They intentionally do NOT import
or instantiate the heavy core under ``src/`` (Database, BudgetEngine,
ImportService). Importing this module must stay side-effect free and error-free.

Phase 1 (bead bud-ayl) replaces these stubs with real singletons, e.g. a
lazily-created Database connection and engine/service instances wired via
FastAPI's ``Depends(...)``. Until then, calling a provider raises
``NotImplementedError`` so accidental wiring fails loudly rather than silently.
"""

# NOTE: keep imports of the core (src.cache.database, src.budget, src.imports)
# OUT of this module until Phase 1. They are heavy and not needed yet.


def get_db():
    """Provide the shared Database singleton. Wired up in Phase 1 (bud-ayl)."""
    raise NotImplementedError("get_db is a Phase 1 placeholder (bead bud-ayl)")


def get_engine():
    """Provide the BudgetEngine singleton. Wired up in Phase 1 (bud-ayl)."""
    raise NotImplementedError("get_engine is a Phase 1 placeholder (bead bud-ayl)")


def get_import_service():
    """Provide the ImportService singleton. Wired up in Phase 1 (bud-ayl)."""
    raise NotImplementedError(
        "get_import_service is a Phase 1 placeholder (bead bud-ayl)"
    )
