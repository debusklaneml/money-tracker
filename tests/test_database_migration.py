"""Upgrade-path coverage for src/cache/database.py.

Exercises the two security-/data-relevant paths added on this branch against a
PRE-EXISTING, old-schema database (every other test builds a fresh DB, so the
migration ALTER and the permission hardening only ever no-op there):
  * `_migrate()` adds `categories.payment_account_id` and the `category_targets`
    table to an old file WITHOUT dropping data, idempotently;
  * `_harden_permissions()` tightens a historically world-readable (0644) DB and
    its directory to 0600 / 0700.
"""

import os
import sqlite3
import stat
import sys

import pytest

from src.cache.database import Database, LOCAL_BUDGET_ID


def _make_old_db(path) -> None:
    """Write a minimal pre-branch DB: categories WITHOUT payment_account_id and
    NO category_targets table, plus one real category row to prove survival."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE budgets (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE categories (
            id TEXT PRIMARY KEY,
            budget_id TEXT NOT NULL,
            category_group_id TEXT,
            category_group_name TEXT,
            name TEXT NOT NULL,
            hidden INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        );
        INSERT INTO budgets (id, name) VALUES ('local', 'My Budget');
        INSERT INTO categories (id, budget_id, category_group_name, name)
            VALUES ('cat-old', 'local', 'Bills', 'Rent');
        """
    )
    conn.commit()
    conn.close()


def _columns(path, table) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        conn.close()


def _table_exists(path, table) -> bool:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() is not None
    finally:
        conn.close()


def test_migrates_old_db_without_data_loss(tmp_path):
    db_path = tmp_path / "old" / "cache.db"
    db_path.parent.mkdir(parents=True)
    _make_old_db(db_path)
    assert "payment_account_id" not in _columns(db_path, "categories")
    assert not _table_exists(db_path, "category_targets")

    # Construct twice to prove the migration is idempotent (no second-run error,
    # no data loss).
    Database(db_path)
    Database(db_path)

    assert "payment_account_id" in _columns(db_path, "categories")
    assert _table_exists(db_path, "category_targets")
    # The pre-existing category survived the upgrade.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM categories WHERE id = 'cat-old'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == "Rent"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission semantics")
def test_hardens_permissions_on_preexisting_db(tmp_path):
    db_path = tmp_path / "vault" / "cache.db"
    db_path.parent.mkdir(parents=True)
    _make_old_db(db_path)
    # Simulate a historically world-readable DB and directory.
    os.chmod(db_path, 0o644)
    os.chmod(db_path.parent, 0o755)

    Database(db_path)

    assert stat.S_IMODE(os.stat(db_path).st_mode) & 0o077 == 0  # 0600, owner-only
    assert stat.S_IMODE(os.stat(db_path.parent).st_mode) == 0o700
