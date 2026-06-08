"""Regression test for bud-3f3: concurrent first-request DB init must not race.

``deps.get_db`` is ``lru_cache``d, but ``lru_cache`` does not serialize concurrent
execution on a cache miss, so a first-request burst (FastAPI's threadpool) can
run multiple ``Database.__init__`` / ``ensure_local_budget`` calls at once.
Before the fix this raced two ways:

* on the one-time rollback->WAL journal-mode switch in ``_get_connection``
  ("database is locked" — the WAL switch does not honour the busy-timeout), and
* on seeding the single budget ("UNIQUE constraint failed: budgets.id").

The fix: ``deps.get_db`` serializes construction with a lock (so the WAL switch
happens single-threaded), and ``ensure_local_budget`` is idempotent via
``BEGIN IMMEDIATE`` + ``INSERT OR IGNORE`` (so the still-concurrent
``get_budget_id`` path can't double-seed or crash).
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import pytest


@pytest.fixture()
def fresh_db_path():
    # Reserve a path then delete the file so the very first connection performs
    # the one-time rollback->WAL switch — the operation that raced.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    db_path.unlink()
    os.environ["BUD_DB_PATH"] = str(db_path)

    from backend import deps

    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()
    try:
        yield db_path
    finally:
        deps.get_db.cache_clear()
        deps.get_budget_id.cache_clear()
        os.environ.pop("BUD_DB_PATH", None)
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()


def test_concurrent_first_request_does_not_race(fresh_db_path):
    from backend import deps
    from src.cache.database import DEFAULT_CATEGORIES

    n = 16
    barrier = threading.Barrier(n)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            # Sync all threads to hit the cold cache simultaneously, then go
            # through get_budget_id -> get_db -> ensure_local_budget: this
            # exercises both the construction path (WAL switch) and the
            # ensure_local_budget path that stays concurrent after the get_db
            # lock.
            barrier.wait()
            deps.get_budget_id()
        except BaseException as exc:  # noqa: BLE001 — record any failure mode
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent first-request init raised: {errors!r}"

    # Seeded exactly once: the default categories with no duplicates.
    db = deps.get_db()
    budget_id = deps.get_budget_id()
    cats = db.get_categories(budget_id, include_hidden=False)
    assert len(cats) == len(DEFAULT_CATEGORIES)
