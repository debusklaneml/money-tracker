"""SQLite database manager for local data caching."""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Iterator
import json


SCHEMA = """
-- Budgets table
CREATE TABLE IF NOT EXISTS budgets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    last_modified_on TEXT,
    first_month TEXT,
    last_month TEXT,
    currency_format TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    on_budget INTEGER,
    closed INTEGER,
    balance INTEGER,
    cleared_balance INTEGER,
    uncleared_balance INTEGER,
    FOREIGN KEY (budget_id) REFERENCES budgets(id)
);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    category_group_id TEXT,
    category_group_name TEXT,
    name TEXT NOT NULL,
    hidden INTEGER DEFAULT 0,
    budgeted INTEGER DEFAULT 0,
    activity INTEGER DEFAULT 0,
    balance INTEGER DEFAULT 0,
    goal_type TEXT,
    goal_target INTEGER,
    goal_target_month TEXT,
    FOREIGN KEY (budget_id) REFERENCES budgets(id)
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    account_id TEXT,
    account_name TEXT,
    date TEXT NOT NULL,
    amount INTEGER NOT NULL,
    memo TEXT,
    cleared TEXT,
    approved INTEGER,
    flag_color TEXT,
    payee_id TEXT,
    payee_name TEXT,
    category_id TEXT,
    category_name TEXT,
    transfer_account_id TEXT,
    transfer_transaction_id TEXT,
    import_id TEXT,
    deleted INTEGER DEFAULT 0,
    FOREIGN KEY (budget_id) REFERENCES budgets(id)
);

-- Scheduled transactions table
CREATE TABLE IF NOT EXISTS scheduled_transactions (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    account_id TEXT,
    account_name TEXT,
    date_first TEXT,
    date_next TEXT,
    frequency TEXT,
    amount INTEGER,
    memo TEXT,
    payee_id TEXT,
    payee_name TEXT,
    category_id TEXT,
    category_name TEXT,
    deleted INTEGER DEFAULT 0,
    FOREIGN KEY (budget_id) REFERENCES budgets(id)
);

-- Monthly budget snapshots
CREATE TABLE IF NOT EXISTS monthly_budgets (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    month TEXT NOT NULL,
    category_id TEXT NOT NULL,
    budgeted INTEGER,
    activity INTEGER,
    balance INTEGER,
    FOREIGN KEY (budget_id) REFERENCES budgets(id)
);

-- Monthly summary: budget-month totals (Ready to Assign, Age of Money, etc.)
CREATE TABLE IF NOT EXISTS monthly_summary (
    budget_id TEXT NOT NULL,
    month TEXT NOT NULL,
    income INTEGER DEFAULT 0,
    budgeted INTEGER DEFAULT 0,
    activity INTEGER DEFAULT 0,
    to_be_budgeted INTEGER DEFAULT 0,
    age_of_money INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (budget_id, month)
);

-- Sync metadata for delta requests
CREATE TABLE IF NOT EXISTS sync_metadata (
    budget_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    last_knowledge_of_server INTEGER,
    last_sync_at TIMESTAMP,
    PRIMARY KEY (budget_id, endpoint)
);

-- Auto-categorization rules: match a payee/memo pattern to a category
CREATE TABLE IF NOT EXISTS category_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id TEXT NOT NULL,
    match_field TEXT NOT NULL DEFAULT 'payee',   -- payee | memo
    match_type TEXT NOT NULL DEFAULT 'contains',  -- contains | equals | regex
    pattern TEXT NOT NULL,
    category_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One row per imported statement file, for dedupe history and undo
CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id TEXT NOT NULL,
    account_id TEXT,
    filename TEXT,
    file_hash TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    txn_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    date_min TEXT,
    date_max TEXT
);

-- Alert history
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    related_entity_id TEXT,
    related_entity_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    dismissed INTEGER DEFAULT 0,
    metadata TEXT
);

-- Per-category funding targets (YNAB-style goals). One row per category.
-- cadence: weekly | monthly | yearly | custom  (custom = every N months)
-- mode:    full | refill
--   full   = set aside the full amount each cycle; balances accumulate.
--   refill = top up the available balance to the target each cycle.
CREATE TABLE IF NOT EXISTS category_targets (
    category_id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    amount_milliunits INTEGER NOT NULL,
    cadence TEXT NOT NULL DEFAULT 'monthly',
    mode TEXT NOT NULL DEFAULT 'refill',
    every_n_months INTEGER DEFAULT 1,   -- for cadence='custom'
    day_of_month INTEGER,               -- optional anchor (1-31)
    month_of_year INTEGER,              -- optional anchor for yearly (1-12)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (budget_id) REFERENCES budgets(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_budget_date ON transactions(budget_id, date);
CREATE INDEX IF NOT EXISTS idx_transactions_payee ON transactions(payee_id);
CREATE INDEX IF NOT EXISTS idx_alerts_budget ON alerts(budget_id, dismissed, created_at);
CREATE INDEX IF NOT EXISTS idx_categories_budget ON categories(budget_id);
CREATE INDEX IF NOT EXISTS idx_monthly_budgets_budget_month ON monthly_budgets(budget_id, month);
"""


# Without YNAB there is a single, local budget. Keep the budget_id plumbing
# (so multi-budget stays possible later) but always use this id.
LOCAL_BUDGET_ID = "local"
LOCAL_BUDGET_NAME = "My Budget"

# Account `type` values (lowercased) treated as credit cards / lines of credit.
# Single source of truth for the credit-vs-cash overspend split — keep the three
# queries that filter on it in lockstep by building the SQL fragment from here.
CREDIT_ACCOUNT_TYPES = ("creditcard", "credit", "creditline", "lineofcredit")
_CREDIT_TYPES_IN = ", ".join(f"'{t}'" for t in CREDIT_ACCOUNT_TYPES)

# Seeded the first time a fresh budget is created; fully editable afterwards.
#
# YNAB-style default structure ("give every dollar a job"), grouped by:
#   - Monthly Bills          : recurring fixed monthly expenses (refill monthly)
#   - Frequent Spending      : variable day-to-day spending (refill monthly)
#   - Non-Monthly Expenses   : "true expenses" that hit irregularly — these are
#                              just accumulating sinking-fund categories, seeded
#                              with yearly/custom targets so money piles up.
#   - Savings Goals          : longer-horizon savings (no target by default)
#   - Quality of Life Goals  : discretionary "fun"/growth goals
#
# Each entry is (group, name, target | None). A target is a dict matching the
# upsert_category_target signature (amount_milliunits, cadence, mode, ...). The
# seed amounts are gentle placeholders (fully editable) so non-monthly expenses
# accumulate sensibly out of the box.
DEFAULT_CATEGORIES = [
    # --- Monthly Bills ---------------------------------------------------
    ("Monthly Bills", "Rent / Mortgage", None),
    ("Monthly Bills", "Electric", None),
    ("Monthly Bills", "Water", None),
    ("Monthly Bills", "Internet", None),
    ("Monthly Bills", "Phone", None),
    # --- Frequent Spending ----------------------------------------------
    ("Frequent Spending", "Groceries", None),
    ("Frequent Spending", "Gas / Fuel", None),
    ("Frequent Spending", "Dining Out", None),
    ("Frequent Spending", "Transportation", None),
    # --- Non-Monthly Expenses (true expenses, accumulating) -------------
    ("Non-Monthly Expenses", "Auto Insurance",
     {"amount_milliunits": 600_000, "cadence": "custom", "mode": "refill",
      "every_n_months": 6}),
    ("Non-Monthly Expenses", "Auto Maintenance",
     {"amount_milliunits": 600_000, "cadence": "yearly", "mode": "refill"}),
    ("Non-Monthly Expenses", "Medical",
     {"amount_milliunits": 1_200_000, "cadence": "yearly", "mode": "refill"}),
    ("Non-Monthly Expenses", "Gifts",
     {"amount_milliunits": 600_000, "cadence": "yearly", "mode": "refill"}),
    ("Non-Monthly Expenses", "Annual Subscriptions",
     {"amount_milliunits": 240_000, "cadence": "yearly", "mode": "refill"}),
    # --- Savings Goals ---------------------------------------------------
    ("Savings Goals", "Emergency Fund", None),
    ("Savings Goals", "Vacation", None),
    ("Savings Goals", "Home / Big Purchases", None),
    # --- Quality of Life Goals ------------------------------------------
    ("Quality of Life Goals", "Hobbies", None),
    ("Quality of Life Goals", "Entertainment", None),
    ("Quality of Life Goals", "Education", None),
]


class Database:
    """SQLite database manager with connection pooling."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".bud" / "cache.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Restrict the parent dir to the owner FIRST, before any DB / WAL / SHM
        # I/O, so nothing inside is reachable by other local users even during
        # the init+seed window (mkdir's mode= is umask-masked, so chmod is the
        # reliable form).
        try:
            os.chmod(self.db_path.parent, 0o700)
        except OSError:
            pass
        # Create the DB and ALL its sidecars owner-only from the first byte. A
        # restrictive umask makes SQLite create the -wal/-shm files 0600 too (it
        # honours the process umask), so the financial history is never even
        # briefly world-readable. The main file is additionally pre-created 0600
        # atomically (O_EXCL) and symlink-safe (O_NOFOLLOW) before sqlite opens
        # it. Construction is serialized by deps.get_db's lock, so the brief
        # process-global umask change is safe.
        old_umask = os.umask(0o077)
        try:
            if not self.db_path.exists():
                flags = (os.O_CREAT | os.O_EXCL | os.O_WRONLY
                         | getattr(os, "O_NOFOLLOW", 0))
                try:
                    os.close(os.open(self.db_path, flags, 0o600))
                except FileExistsError:
                    pass
            self._init_schema()
            self._migrate()
            self.ensure_local_budget()
        finally:
            os.umask(old_umask)
        # Belt-and-suspenders: tighten sidecar modes and any pre-existing
        # historically-0644 database / 0755 directory.
        self._harden_permissions()

    def _harden_permissions(self) -> None:
        """Restrict the DB and its parent dir to the owner only.

        Tightens the DB file and its WAL/SHM sidecars to 0600 and the
        containing directory to 0700, covering both freshly-created and
        pre-existing (historically 0644) databases. Best-effort: permission
        semantics vary across platforms, so failures here must never block
        startup.
        """
        try:
            os.chmod(self.db_path.parent, 0o700)
        except OSError:
            pass
        for sidecar in ("", "-wal", "-shm"):
            path = (
                self.db_path
                if not sidecar
                else self.db_path.with_name(self.db_path.name + sidecar)
            )
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)

    def _migrate(self) -> None:
        """Add columns introduced after the original schema. Safe to re-run."""
        migrations = [
            "ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0",
            "ALTER TABLE accounts ADD COLUMN account_number TEXT",
            "ALTER TABLE transactions ADD COLUMN import_batch_id INTEGER",
            # Credit-card handling: a "payment" category is linked to the credit
            # account it pays. NULL for ordinary spending categories.
            "ALTER TABLE categories ADD COLUMN payment_account_id TEXT",
        ]
        with self._get_connection() as conn:
            for stmt in migrations:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass  # column already exists
            # Collapse any duplicate credit-card payment categories left by an
            # older non-atomic ensure_payment_category, then enforce uniqueness
            # so the race can never recur. (Dedupe must precede the unique index,
            # which would otherwise fail to build on an already-duplicated DB.)
            self._dedupe_payment_categories(conn)
            try:
                conn.execute(
                    """CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_payment_account
                       ON categories(budget_id, payment_account_id)
                       WHERE payment_account_id IS NOT NULL"""
                )
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _dedupe_payment_categories(conn: sqlite3.Connection) -> None:
        """Keep one payment category per (budget_id, account); repoint & drop dups."""
        dup_groups = conn.execute(
            """SELECT budget_id, payment_account_id
               FROM categories
               WHERE payment_account_id IS NOT NULL
               GROUP BY budget_id, payment_account_id
               HAVING COUNT(*) > 1"""
        ).fetchall()
        for budget_id, account_id in dup_groups:
            rows = conn.execute(
                """SELECT id FROM categories
                   WHERE budget_id = ? AND payment_account_id = ?
                   ORDER BY sort_order, rowid""",
                (budget_id, account_id),
            ).fetchall()
            keep = rows[0]["id"]
            for extra in rows[1:]:
                dead = extra["id"]
                # Move any assignments/activity on the dup onto the survivor.
                conn.execute(
                    "UPDATE monthly_budgets SET category_id = ? WHERE category_id = ?",
                    (keep, dead),
                )
                conn.execute(
                    "UPDATE transactions SET category_id = ? WHERE category_id = ?",
                    (keep, dead),
                )
                conn.execute("DELETE FROM category_targets WHERE category_id = ?", (dead,))
                conn.execute("DELETE FROM categories WHERE id = ?", (dead,))

    def ensure_local_budget(self) -> str:
        """Ensure the single local budget exists, seeding default categories once.

        Idempotent and concurrency-safe. ``Database`` construction is serialized
        by ``deps.get_db``'s lock, but this method is also reachable directly via
        ``deps.get_budget_id`` (itself ``lru_cache``d, which does not serialize
        concurrent cache misses), so two threads can still call it at once. We
        take the write lock up front with ``BEGIN IMMEDIATE`` (the second caller
        blocks until the first commits and then sees the seeded rows) and use
        ``INSERT OR IGNORE`` as a belt-and-suspenders guard against duplicate
        inserts.
        """
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute(
                "SELECT 1 FROM budgets WHERE id = ?", (LOCAL_BUDGET_ID,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT OR IGNORE INTO budgets (id, name) VALUES (?, ?)",
                    (LOCAL_BUDGET_ID, LOCAL_BUDGET_NAME),
                )
            has_categories = conn.execute(
                "SELECT 1 FROM categories WHERE budget_id = ? LIMIT 1", (LOCAL_BUDGET_ID,)
            ).fetchone()
            if not has_categories:
                for order, (group, name, target) in enumerate(DEFAULT_CATEGORIES):
                    cat_id = uuid.uuid4().hex
                    conn.execute(
                        """INSERT INTO categories
                           (id, budget_id, category_group_id, category_group_name, name, sort_order)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (cat_id, LOCAL_BUDGET_ID, group.lower(), group, name, order),
                    )
                    if target is not None:
                        conn.execute(
                            """INSERT OR IGNORE INTO category_targets
                               (category_id, budget_id, amount_milliunits, cadence,
                                mode, every_n_months, day_of_month, month_of_year)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (cat_id, LOCAL_BUDGET_ID,
                             target["amount_milliunits"],
                             target.get("cadence", "monthly"),
                             target.get("mode", "refill"),
                             target.get("every_n_months", 1),
                             target.get("day_of_month"),
                             target.get("month_of_year")),
                        )
        return LOCAL_BUDGET_ID

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with optimizations."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Budget operations
    def upsert_budget(self, budget_id: str, name: str, last_modified_on: str,
                      first_month: str, last_month: str, currency_format: Optional[str] = None) -> None:
        """Insert or update a budget."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO budgets (id, name, last_modified_on, first_month, last_month, currency_format, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    last_modified_on = excluded.last_modified_on,
                    first_month = excluded.first_month,
                    last_month = excluded.last_month,
                    currency_format = excluded.currency_format,
                    updated_at = excluded.updated_at
            """, (budget_id, name, last_modified_on, first_month, last_month, currency_format, datetime.utcnow()))

    def get_budgets(self) -> list[sqlite3.Row]:
        """Get all budgets."""
        with self._get_connection() as conn:
            return conn.execute("SELECT * FROM budgets ORDER BY name").fetchall()

    def get_budget(self, budget_id: str) -> Optional[sqlite3.Row]:
        """Get a specific budget."""
        with self._get_connection() as conn:
            return conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()

    # Account operations
    def upsert_account(self, account_id: str, budget_id: str, name: str, account_type: str,
                       on_budget: bool, closed: bool, balance: int,
                       cleared_balance: int, uncleared_balance: int) -> None:
        """Insert or update an account."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO accounts (id, budget_id, name, type, on_budget, closed, balance, cleared_balance, uncleared_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    on_budget = excluded.on_budget,
                    closed = excluded.closed,
                    balance = excluded.balance,
                    cleared_balance = excluded.cleared_balance,
                    uncleared_balance = excluded.uncleared_balance
            """, (account_id, budget_id, name, account_type, int(on_budget), int(closed),
                  balance, cleared_balance, uncleared_balance))

    def get_accounts(self, budget_id: str) -> list[sqlite3.Row]:
        """Get all accounts for a budget."""
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM accounts WHERE budget_id = ? ORDER BY name",
                (budget_id,)
            ).fetchall()

    # Category operations
    def upsert_category(self, category_id: str, budget_id: str, category_group_id: str,
                        category_group_name: str, name: str, hidden: bool, budgeted: int,
                        activity: int, balance: int, goal_type: Optional[str],
                        goal_target: Optional[int], goal_target_month: Optional[str]) -> None:
        """Insert or update a category."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO categories (id, budget_id, category_group_id, category_group_name, name, hidden, budgeted, activity, balance, goal_type, goal_target, goal_target_month)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category_group_id = excluded.category_group_id,
                    category_group_name = excluded.category_group_name,
                    name = excluded.name,
                    hidden = excluded.hidden,
                    budgeted = excluded.budgeted,
                    activity = excluded.activity,
                    balance = excluded.balance,
                    goal_type = excluded.goal_type,
                    goal_target = excluded.goal_target,
                    goal_target_month = excluded.goal_target_month
            """, (category_id, budget_id, category_group_id, category_group_name, name,
                  int(hidden), budgeted, activity, balance, goal_type, goal_target, goal_target_month))

    def get_categories(self, budget_id: str, include_hidden: bool = False) -> list[sqlite3.Row]:
        """Get all categories for a budget."""
        with self._get_connection() as conn:
            if include_hidden:
                return conn.execute(
                    "SELECT * FROM categories WHERE budget_id = ? ORDER BY category_group_name, name",
                    (budget_id,)
                ).fetchall()
            return conn.execute(
                "SELECT * FROM categories WHERE budget_id = ? AND hidden = 0 ORDER BY category_group_name, name",
                (budget_id,)
            ).fetchall()

    def get_category(self, category_id: str) -> Optional[sqlite3.Row]:
        """Get a specific category."""
        with self._get_connection() as conn:
            return conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    # Transaction operations
    def upsert_transaction(self, txn_id: str, budget_id: str, account_id: str, account_name: str,
                           txn_date: str, amount: int, memo: Optional[str], cleared: str,
                           approved: bool, flag_color: Optional[str], payee_id: Optional[str],
                           payee_name: Optional[str], category_id: Optional[str],
                           category_name: Optional[str], transfer_account_id: Optional[str],
                           transfer_transaction_id: Optional[str], import_id: Optional[str],
                           deleted: bool) -> None:
        """Insert or update a transaction."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO transactions (id, budget_id, account_id, account_name, date, amount, memo, cleared, approved, flag_color, payee_id, payee_name, category_id, category_name, transfer_account_id, transfer_transaction_id, import_id, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    account_id = excluded.account_id,
                    account_name = excluded.account_name,
                    date = excluded.date,
                    amount = excluded.amount,
                    memo = excluded.memo,
                    cleared = excluded.cleared,
                    approved = excluded.approved,
                    flag_color = excluded.flag_color,
                    payee_id = excluded.payee_id,
                    payee_name = excluded.payee_name,
                    category_id = excluded.category_id,
                    category_name = excluded.category_name,
                    transfer_account_id = excluded.transfer_account_id,
                    transfer_transaction_id = excluded.transfer_transaction_id,
                    import_id = excluded.import_id,
                    deleted = excluded.deleted
            """, (txn_id, budget_id, account_id, account_name, txn_date, amount, memo, cleared,
                  int(approved), flag_color, payee_id, payee_name, category_id, category_name,
                  transfer_account_id, transfer_transaction_id, import_id, int(deleted)))

    def get_transactions(self, budget_id: str, limit: int = 100, offset: int = 0,
                         include_deleted: bool = False) -> list[sqlite3.Row]:
        """Get transactions for a budget."""
        with self._get_connection() as conn:
            if include_deleted:
                return conn.execute(
                    "SELECT * FROM transactions WHERE budget_id = ? ORDER BY date DESC LIMIT ? OFFSET ?",
                    (budget_id, limit, offset)
                ).fetchall()
            return conn.execute(
                "SELECT * FROM transactions WHERE budget_id = ? AND deleted = 0 ORDER BY date DESC LIMIT ? OFFSET ?",
                (budget_id, limit, offset)
            ).fetchall()

    def get_recent_transactions(self, budget_id: str, days: int = 30) -> list[sqlite3.Row]:
        """Get recent transactions within specified days."""
        with self._get_connection() as conn:
            return conn.execute("""
                SELECT * FROM transactions
                WHERE budget_id = ? AND deleted = 0
                AND date >= date('now', ?)
                ORDER BY date DESC
            """, (budget_id, f'-{days} days')).fetchall()

    def get_category_transactions(self, budget_id: str, category_id: str,
                                   months: int = 6, exclude_id: Optional[str] = None) -> list[sqlite3.Row]:
        """Get transactions for a specific category."""
        with self._get_connection() as conn:
            if exclude_id:
                return conn.execute("""
                    SELECT * FROM transactions
                    WHERE budget_id = ? AND category_id = ? AND deleted = 0
                    AND id != ?
                    AND date >= date('now', ?)
                    ORDER BY date DESC
                """, (budget_id, category_id, exclude_id, f'-{months} months')).fetchall()
            return conn.execute("""
                SELECT * FROM transactions
                WHERE budget_id = ? AND category_id = ? AND deleted = 0
                AND date >= date('now', ?)
                ORDER BY date DESC
            """, (budget_id, category_id, f'-{months} months')).fetchall()

    def get_transactions_by_payee(self, budget_id: str, payee_id: str, days: int = 60) -> list[sqlite3.Row]:
        """Get transactions for a specific payee."""
        with self._get_connection() as conn:
            return conn.execute("""
                SELECT * FROM transactions
                WHERE budget_id = ? AND payee_id = ? AND deleted = 0
                AND date >= date('now', ?)
                ORDER BY date DESC
            """, (budget_id, payee_id, f'-{days} days')).fetchall()

    def find_matching_transaction(self, budget_id: str, payee_id: str,
                                   date_start: date, date_end: date,
                                   amount: int, tolerance: int = 100) -> Optional[sqlite3.Row]:
        """Find a transaction matching criteria within tolerance."""
        with self._get_connection() as conn:
            return conn.execute("""
                SELECT * FROM transactions
                WHERE budget_id = ? AND payee_id = ? AND deleted = 0
                AND date BETWEEN ? AND ?
                AND ABS(amount - ?) <= ?
                LIMIT 1
            """, (budget_id, payee_id, date_start.isoformat(), date_end.isoformat(),
                  amount, tolerance)).fetchone()

    # Scheduled transaction operations
    def upsert_scheduled_transaction(self, sched_id: str, budget_id: str, account_id: str,
                                      account_name: str, date_first: str, date_next: str,
                                      frequency: str, amount: int, memo: Optional[str],
                                      payee_id: Optional[str], payee_name: Optional[str],
                                      category_id: Optional[str], category_name: Optional[str],
                                      deleted: bool) -> None:
        """Insert or update a scheduled transaction."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO scheduled_transactions (id, budget_id, account_id, account_name, date_first, date_next, frequency, amount, memo, payee_id, payee_name, category_id, category_name, deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    account_id = excluded.account_id,
                    account_name = excluded.account_name,
                    date_first = excluded.date_first,
                    date_next = excluded.date_next,
                    frequency = excluded.frequency,
                    amount = excluded.amount,
                    memo = excluded.memo,
                    payee_id = excluded.payee_id,
                    payee_name = excluded.payee_name,
                    category_id = excluded.category_id,
                    category_name = excluded.category_name,
                    deleted = excluded.deleted
            """, (sched_id, budget_id, account_id, account_name, date_first, date_next,
                  frequency, amount, memo, payee_id, payee_name, category_id, category_name, int(deleted)))

    def get_scheduled_transactions(self, budget_id: str) -> list[sqlite3.Row]:
        """Get all scheduled transactions for a budget."""
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM scheduled_transactions WHERE budget_id = ? AND deleted = 0 ORDER BY date_next",
                (budget_id,)
            ).fetchall()

    # Monthly budget operations
    def upsert_monthly_budget(self, budget_id: str, month: str, category_id: str,
                               budgeted: int, activity: int, balance: int) -> None:
        """Insert or update a monthly budget entry."""
        record_id = f"{budget_id}_{month}_{category_id}"
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO monthly_budgets (id, budget_id, month, category_id, budgeted, activity, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    budgeted = excluded.budgeted,
                    activity = excluded.activity,
                    balance = excluded.balance
            """, (record_id, budget_id, month, category_id, budgeted, activity, balance))

    def get_monthly_budgets(self, budget_id: str, month: str) -> list[sqlite3.Row]:
        """Get monthly budget entries."""
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM monthly_budgets WHERE budget_id = ? AND month = ?",
                (budget_id, month)
            ).fetchall()

    def update_monthly_budget_amounts(self, budget_id: str, month: str, category_id: str,
                                       budgeted: int, activity: int, balance: int) -> None:
        """Update budgeted/activity/balance for a single category-month after a write-back."""
        self.upsert_monthly_budget(budget_id, month, category_id, budgeted, activity, balance)
        # Keep the categories table (used by the dashboard) in sync for the current month.
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE categories SET budgeted = ?, activity = ?, balance = ? WHERE id = ?",
                (budgeted, activity, balance, category_id)
            )

    # Monthly summary operations
    def upsert_monthly_summary(self, budget_id: str, month: str, income: int, budgeted: int,
                               activity: int, to_be_budgeted: int,
                               age_of_money: Optional[int]) -> None:
        """Insert or update a budget-month summary (Ready to Assign, Age of Money, ...)."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO monthly_summary (budget_id, month, income, budgeted, activity, to_be_budgeted, age_of_money, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(budget_id, month) DO UPDATE SET
                    income = excluded.income,
                    budgeted = excluded.budgeted,
                    activity = excluded.activity,
                    to_be_budgeted = excluded.to_be_budgeted,
                    age_of_money = excluded.age_of_money,
                    updated_at = excluded.updated_at
            """, (budget_id, month, income, budgeted, activity, to_be_budgeted,
                  age_of_money, datetime.now()))

    def get_monthly_summary(self, budget_id: str, month: str) -> Optional[sqlite3.Row]:
        """Get the summary row for a budget-month, or None if not synced yet."""
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM monthly_summary WHERE budget_id = ? AND month = ?",
                (budget_id, month)
            ).fetchone()

    # Sync metadata operations
    def get_sync_knowledge(self, budget_id: str, endpoint: str) -> Optional[int]:
        """Get last knowledge of server for delta sync."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT last_knowledge_of_server FROM sync_metadata WHERE budget_id = ? AND endpoint = ?",
                (budget_id, endpoint)
            ).fetchone()
            return row['last_knowledge_of_server'] if row else None

    def update_sync_knowledge(self, budget_id: str, endpoint: str, knowledge: int) -> None:
        """Update sync knowledge after successful sync."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO sync_metadata (budget_id, endpoint, last_knowledge_of_server, last_sync_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(budget_id, endpoint) DO UPDATE SET
                    last_knowledge_of_server = excluded.last_knowledge_of_server,
                    last_sync_at = excluded.last_sync_at
            """, (budget_id, endpoint, knowledge, datetime.utcnow()))

    def get_last_sync(self, budget_id: str) -> Optional[datetime]:
        """Get the most recent sync timestamp for a budget."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(last_sync_at) as last_sync FROM sync_metadata WHERE budget_id = ?",
                (budget_id,)
            ).fetchone()
            if row and row['last_sync']:
                return datetime.fromisoformat(row['last_sync'])
            return None

    # Alert operations
    def save_alert(self, budget_id: str, alert_type: str, severity: str, title: str,
                   description: str, related_entity_id: Optional[str] = None,
                   related_entity_type: Optional[str] = None,
                   metadata: Optional[dict] = None) -> int:
        """Save a new alert and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO alerts (budget_id, alert_type, severity, title, description, related_entity_id, related_entity_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (budget_id, alert_type, severity, title, description, related_entity_id,
                  related_entity_type, json.dumps(metadata) if metadata else None))
            return cursor.lastrowid

    def get_alerts(self, budget_id: str, include_dismissed: bool = False,
                   severities: Optional[list[str]] = None,
                   alert_types: Optional[list[str]] = None,
                   limit: int = 100) -> list[sqlite3.Row]:
        """Get alerts with optional filtering."""
        conditions = ["budget_id = ?"]
        params: list = [budget_id]

        if not include_dismissed:
            conditions.append("dismissed = 0")

        if severities:
            placeholders = ",".join("?" * len(severities))
            conditions.append(f"severity IN ({placeholders})")
            params.extend(severities)

        if alert_types:
            placeholders = ",".join("?" * len(alert_types))
            conditions.append(f"alert_type IN ({placeholders})")
            params.extend(alert_types)

        params.append(limit)

        with self._get_connection() as conn:
            return conn.execute(f"""
                SELECT * FROM alerts
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ?
            """, params).fetchall()

    def get_active_alerts(self, budget_id: str, limit: int = 10) -> list[sqlite3.Row]:
        """Get active (non-dismissed) alerts."""
        return self.get_alerts(budget_id, include_dismissed=False, limit=limit)

    def acknowledge_alert(self, alert_id: int) -> None:
        """Mark an alert as acknowledged."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE alerts SET acknowledged_at = ? WHERE id = ?",
                (datetime.utcnow(), alert_id)
            )

    def dismiss_alert(self, alert_id: int) -> None:
        """Dismiss an alert."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE alerts SET dismissed = 1 WHERE id = ?",
                (alert_id,)
            )

    def alert_exists(self, budget_id: str, alert_type: str, related_entity_id: str) -> bool:
        """Check if an alert already exists (to avoid duplicates)."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT 1 FROM alerts
                WHERE budget_id = ? AND alert_type = ? AND related_entity_id = ? AND dismissed = 0
                LIMIT 1
            """, (budget_id, alert_type, related_entity_id)).fetchone()
            return row is not None

    # Analytics queries
    def get_spending_by_category(self, budget_id: str, months: int = 1) -> list[sqlite3.Row]:
        """Get total spending grouped by category."""
        with self._get_connection() as conn:
            return conn.execute("""
                SELECT category_id, category_name, SUM(ABS(amount)) as total_amount, COUNT(*) as transaction_count
                FROM transactions
                WHERE budget_id = ? AND deleted = 0 AND amount < 0
                AND date >= date('now', ?)
                GROUP BY category_id, category_name
                ORDER BY total_amount DESC
            """, (budget_id, f'-{months} months')).fetchall()

    def get_monthly_spending_trend(self, budget_id: str, months: int = 12) -> list[sqlite3.Row]:
        """Get monthly spending totals."""
        with self._get_connection() as conn:
            return conn.execute("""
                SELECT strftime('%Y-%m', date) as month, SUM(ABS(amount)) as total_amount
                FROM transactions
                WHERE budget_id = ? AND deleted = 0 AND amount < 0
                AND date >= date('now', ?)
                GROUP BY strftime('%Y-%m', date)
                ORDER BY month
            """, (budget_id, f'-{months} months')).fetchall()

    def get_current_month_categories(self, budget_id: str) -> list[sqlite3.Row]:
        """Get categories with current month budget data."""
        current_month = datetime.now().strftime('%Y-%m-01')
        with self._get_connection() as conn:
            return conn.execute("""
                SELECT c.*, mb.budgeted as month_budgeted, mb.activity as month_activity, mb.balance as month_balance
                FROM categories c
                LEFT JOIN monthly_budgets mb ON c.id = mb.category_id AND mb.month = ?
                WHERE c.budget_id = ? AND c.hidden = 0
                ORDER BY c.category_group_name, c.name
            """, (current_month, budget_id)).fetchall()

    # ------------------------------------------------------------------
    # Category management (local, user-owned)
    # ------------------------------------------------------------------
    def create_category(self, budget_id: str, group: str, name: str) -> str:
        """Create a new category; returns its id."""
        cat_id = uuid.uuid4().hex
        with self._get_connection() as conn:
            next_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM categories WHERE budget_id = ?",
                (budget_id,),
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO categories
                   (id, budget_id, category_group_id, category_group_name, name, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cat_id, budget_id, group.lower(), group, name, next_order),
            )
        return cat_id

    def update_category(self, category_id: str, name: str, group: str) -> None:
        """Rename a category and/or move it to another group."""
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE categories
                   SET name = ?, category_group_name = ?, category_group_id = ?
                   WHERE id = ?""",
                (name, group, group.lower(), category_id),
            )

    def set_category_hidden(self, category_id: str, hidden: bool) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE categories SET hidden = ? WHERE id = ?",
                (int(hidden), category_id),
            )

    def delete_category(self, category_id: str) -> None:
        """Delete a category; its transactions fall back to uncategorized."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE transactions SET category_id = NULL, category_name = NULL WHERE category_id = ?",
                (category_id,),
            )
            conn.execute("DELETE FROM monthly_budgets WHERE category_id = ?", (category_id,))
            conn.execute("DELETE FROM category_rules WHERE category_id = ?", (category_id,))
            # FK enforcement / ON DELETE CASCADE is not enabled, so clear the
            # category's funding target explicitly or it lingers as an orphan.
            conn.execute("DELETE FROM category_targets WHERE category_id = ?", (category_id,))
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    # ------------------------------------------------------------------
    # Category targets (YNAB-style funding goals)
    # ------------------------------------------------------------------
    def upsert_category_target(self, budget_id: str, category_id: str,
                               amount_milliunits: int, cadence: str = "monthly",
                               mode: str = "refill", every_n_months: int = 1,
                               day_of_month: Optional[int] = None,
                               month_of_year: Optional[int] = None) -> None:
        """Create or replace a category's funding target."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO category_targets
                   (category_id, budget_id, amount_milliunits, cadence, mode,
                    every_n_months, day_of_month, month_of_year)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(category_id) DO UPDATE SET
                       amount_milliunits = excluded.amount_milliunits,
                       cadence = excluded.cadence,
                       mode = excluded.mode,
                       every_n_months = excluded.every_n_months,
                       day_of_month = excluded.day_of_month,
                       month_of_year = excluded.month_of_year""",
                (category_id, budget_id, amount_milliunits, cadence, mode,
                 every_n_months, day_of_month, month_of_year),
            )

    def get_category_target(self, category_id: str) -> Optional[sqlite3.Row]:
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM category_targets WHERE category_id = ?",
                (category_id,),
            ).fetchone()

    def get_category_targets(self, budget_id: str) -> dict[str, sqlite3.Row]:
        """All targets for a budget, keyed by category_id."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM category_targets WHERE budget_id = ?",
                (budget_id,),
            ).fetchall()
        return {r["category_id"]: r for r in rows}

    def delete_category_target(self, category_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM category_targets WHERE category_id = ?",
                (category_id,),
            )

    # ------------------------------------------------------------------
    # Credit-card payment categories
    # ------------------------------------------------------------------
    def get_credit_accounts(self, budget_id: str) -> list[sqlite3.Row]:
        """Accounts whose type marks them as credit (credit cards / lines)."""
        with self._get_connection() as conn:
            return conn.execute(
                f"""SELECT * FROM accounts
                   WHERE budget_id = ? AND closed = 0
                     AND LOWER(COALESCE(type, '')) IN ({_CREDIT_TYPES_IN})""",
                (budget_id,),
            ).fetchall()

    def get_payment_category_for_account(self, budget_id: str,
                                         account_id: str) -> Optional[sqlite3.Row]:
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM categories WHERE budget_id = ? AND payment_account_id = ?",
                (budget_id, account_id),
            ).fetchone()

    def payment_categories_by_account(self, budget_id: str) -> dict[str, str]:
        """Map ``account_id -> payment_category_id`` for the budget's credit cards.

        One SELECT for the whole (month-invariant) mapping, so the budget-state
        walk doesn't re-query per account per month.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT payment_account_id, id FROM categories
                   WHERE budget_id = ? AND payment_account_id IS NOT NULL""",
                (budget_id,),
            ).fetchall()
        return {r["payment_account_id"]: r["id"] for r in rows}

    def ensure_payment_category(self, budget_id: str, account_id: str,
                                account_name: str) -> str:
        """Create (idempotently) the payment category for a credit account.

        Returns the category id. The category lives in a 'Credit Card Payments'
        group and carries ``payment_account_id`` linking it back to the account.

        Concurrency-safe: ``BEGIN IMMEDIATE`` takes the write lock up front so two
        concurrent first-time syncs serialize (the second sees the row the first
        inserted and returns it), and a partial unique index on
        ``(budget_id, payment_account_id)`` is the hard backstop.
        """
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT id FROM categories WHERE budget_id = ? AND payment_account_id = ?",
                (budget_id, account_id),
            ).fetchone()
            if existing is not None:
                return existing["id"]
            cat_id = uuid.uuid4().hex
            next_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM categories WHERE budget_id = ?",
                (budget_id,),
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO categories
                   (id, budget_id, category_group_id, category_group_name, name,
                    sort_order, payment_account_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cat_id, budget_id, "credit_card_payments", "Credit Card Payments",
                 account_name, next_order, account_id),
            )
        return cat_id

    def sync_payment_categories(self, budget_id: str) -> list[str]:
        """Ensure every credit account has a payment category. Returns their ids."""
        ids = []
        for acct in self.get_credit_accounts(budget_id):
            ids.append(self.ensure_payment_category(budget_id, acct["id"], acct["name"]))
        return ids

    def credit_activity_in_month(self, budget_id: str, month: str) -> dict[str, int]:
        """Per *credit-account* net categorized activity in ``month``.

        Keyed by account_id. Used to compute how much each card's payment
        category needs (a spend on a credit card increases the payment need).
        Only counts on-budget categorized transactions on credit accounts.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                f"""SELECT t.account_id, SUM(t.amount)
                   FROM transactions t JOIN accounts a ON t.account_id = a.id
                   WHERE t.budget_id = ? AND t.deleted = 0
                     AND t.category_id IS NOT NULL
                     AND strftime('%Y-%m-01', t.date) = ?
                     AND LOWER(COALESCE(a.type, '')) IN ({_CREDIT_TYPES_IN})
                   GROUP BY t.account_id""",
                (budget_id, month),
            ).fetchall()
        return {r[0]: int(r[1] or 0) for r in rows}

    def credit_activity_by_category_in_month(self, budget_id: str,
                                             month: str) -> dict[str, int]:
        """Per *spending category* the net activity that landed on credit cards
        in ``month`` (keyed by category_id, outflows negative).

        This is the portion of a category's monthly activity that should become
        card debt rather than cash overspend. Payment categories are excluded
        (their own funding is cash).
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                f"""SELECT t.category_id, SUM(t.amount)
                   FROM transactions t JOIN accounts a ON t.account_id = a.id
                   WHERE t.budget_id = ? AND t.deleted = 0
                     AND t.category_id IS NOT NULL
                     AND strftime('%Y-%m-01', t.date) = ?
                     AND LOWER(COALESCE(a.type, '')) IN ({_CREDIT_TYPES_IN})
                   GROUP BY t.category_id""",
                (budget_id, month),
            ).fetchall()
        return {r[0]: int(r[1] or 0) for r in rows}

    # ------------------------------------------------------------------
    # Imports: accounts, dedupe, and inserting parsed transactions
    # ------------------------------------------------------------------
    def upsert_imported_account(self, budget_id: str, account_number: str, name: str,
                                account_type: str, on_budget: bool,
                                balance: int) -> str:
        """Create/update an account keyed by its bank account number; returns id."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM accounts WHERE budget_id = ? AND account_number = ?",
                (budget_id, account_number),
            ).fetchone()
            account_id = row["id"] if row else uuid.uuid4().hex
            conn.execute(
                """INSERT INTO accounts
                   (id, budget_id, name, type, on_budget, closed, balance,
                    cleared_balance, uncleared_balance, account_number)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?, 0, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       name = excluded.name,
                       type = excluded.type,
                       balance = excluded.balance,
                       cleared_balance = excluded.cleared_balance,
                       account_number = excluded.account_number""",
                (account_id, budget_id, name, account_type, int(on_budget),
                 balance, balance, account_number),
            )
        return account_id

    def transaction_exists(self, account_id: str, fitid: str) -> bool:
        """Dedupe check: has this bank FITID already been imported for this account?"""
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT 1 FROM transactions WHERE account_id = ? AND import_id = ? LIMIT 1",
                (account_id, fitid),
            ).fetchone() is not None

    def insert_imported_transaction(self, budget_id: str, account_id: str, account_name: str,
                                    fitid: str, txn_date: str, amount: int,
                                    payee_name: Optional[str], memo: Optional[str],
                                    category_id: Optional[str], category_name: Optional[str],
                                    import_batch_id: int) -> str:
        """Insert one parsed transaction. import_id holds the bank FITID."""
        txn_id = uuid.uuid4().hex
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO transactions
                   (id, budget_id, account_id, account_name, date, amount, memo,
                    cleared, approved, payee_name, category_id, category_name,
                    import_id, import_batch_id, deleted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'cleared', 1, ?, ?, ?, ?, ?, 0)""",
                (txn_id, budget_id, account_id, account_name, txn_date, amount, memo,
                 payee_name, category_id, category_name, fitid, import_batch_id),
            )
        return txn_id

    def create_import_batch(self, budget_id: str, account_id: Optional[str], filename: str,
                            file_hash: str) -> int:
        with self._get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO import_batches (budget_id, account_id, filename, file_hash)
                   VALUES (?, ?, ?, ?)""",
                (budget_id, account_id, filename, file_hash),
            )
            return cur.lastrowid

    def finalize_import_batch(self, batch_id: int, txn_count: int, duplicate_count: int,
                              date_min: Optional[str], date_max: Optional[str]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE import_batches
                   SET txn_count = ?, duplicate_count = ?, date_min = ?, date_max = ?
                   WHERE id = ?""",
                (txn_count, duplicate_count, date_min, date_max, batch_id),
            )

    def file_hash_imported(self, budget_id: str, file_hash: str) -> bool:
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT 1 FROM import_batches WHERE budget_id = ? AND file_hash = ? AND txn_count > 0 LIMIT 1",
                (budget_id, file_hash),
            ).fetchone() is not None

    def get_import_batches(self, budget_id: str, limit: int = 50) -> list[sqlite3.Row]:
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM import_batches WHERE budget_id = ? ORDER BY imported_at DESC LIMIT ?",
                (budget_id, limit),
            ).fetchall()

    def delete_import_batch(self, budget_id: str, batch_id: int) -> Optional[int]:
        """Delete an import batch and cascade-delete its transactions, atomically.

        Returns the number of transactions removed, or ``None`` if no batch with
        that id exists for the budget (so the caller can surface a 404). Both
        deletes share one connection/transaction: either everything is removed
        or nothing is. Once the batch row is gone its file_hash is no longer in
        ``import_batches``, so :meth:`file_hash_imported` reports the file as
        importable again and re-importing the same file works.
        """
        with self._get_connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM import_batches WHERE budget_id = ? AND id = ?",
                (budget_id, batch_id),
            ).fetchone()
            if exists is None:
                return None
            cur = conn.execute(
                "DELETE FROM transactions WHERE budget_id = ? AND import_batch_id = ?",
                (budget_id, batch_id),
            )
            deleted = cur.rowcount
            conn.execute(
                "DELETE FROM import_batches WHERE budget_id = ? AND id = ?",
                (budget_id, batch_id),
            )
            return deleted

    # ------------------------------------------------------------------
    # Transaction categorization
    # ------------------------------------------------------------------
    def set_transaction_category(self, txn_id: str, category_id: Optional[str],
                                 category_name: Optional[str]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE transactions SET category_id = ?, category_name = ? WHERE id = ?",
                (category_id, category_name, txn_id),
            )

    def get_uncategorized_transactions(self, budget_id: str, limit: int = 500) -> list[sqlite3.Row]:
        with self._get_connection() as conn:
            return conn.execute(
                """SELECT * FROM transactions
                   WHERE budget_id = ? AND deleted = 0 AND category_id IS NULL
                   ORDER BY date DESC LIMIT ?""",
                (budget_id, limit),
            ).fetchall()

    def count_uncategorized(self, budget_id: str) -> int:
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE budget_id = ? AND deleted = 0 AND category_id IS NULL",
                (budget_id,),
            ).fetchone()[0]

    # ------------------------------------------------------------------
    # Auto-categorization rules
    # ------------------------------------------------------------------
    def add_rule(self, budget_id: str, pattern: str, category_id: str,
                 match_field: str = "payee", match_type: str = "contains",
                 priority: int = 100) -> int:
        with self._get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO category_rules
                   (budget_id, match_field, match_type, pattern, category_id, priority)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (budget_id, match_field, match_type, pattern, category_id, priority),
            )
            return cur.lastrowid

    def get_rules(self, budget_id: str) -> list[sqlite3.Row]:
        with self._get_connection() as conn:
            return conn.execute(
                """SELECT r.*, c.name AS category_name, c.category_group_name AS group_name
                   FROM category_rules r JOIN categories c ON r.category_id = c.id
                   WHERE r.budget_id = ? ORDER BY r.priority, r.id""",
                (budget_id,),
            ).fetchall()

    def delete_rule(self, rule_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))

    # ------------------------------------------------------------------
    # Engine aggregates (money in milliunits)
    # ------------------------------------------------------------------
    def _sum_map(self, sql: str, params: tuple) -> dict[str, int]:
        with self._get_connection() as conn:
            return {r[0]: int(r[1] or 0) for r in conn.execute(sql, params).fetchall()}

    def assigned_by_category(self, budget_id: str, through_month: str) -> dict[str, int]:
        """Cumulative assigned per category for all months up to and incl. through_month."""
        return self._sum_map(
            """SELECT category_id, SUM(budgeted) FROM monthly_budgets
               WHERE budget_id = ? AND month <= ? GROUP BY category_id""",
            (budget_id, through_month),
        )

    def active_months(self, budget_id: str, through_month: str) -> list[str]:
        """Distinct budget months (YYYY-MM-01) that have any assignment or activity,
        up to and including ``through_month``. Used by the engine to walk month
        boundaries when rolling cash overspend into Ready to Assign.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT month FROM monthly_budgets
                       WHERE budget_id = ? AND month <= ?
                   UNION
                   SELECT strftime('%Y-%m-01', date) AS month FROM transactions
                       WHERE budget_id = ? AND deleted = 0 AND category_id IS NOT NULL
                         AND strftime('%Y-%m-01', date) <= ?""",
                (budget_id, through_month, budget_id, through_month),
            ).fetchall()
        return sorted({r[0] for r in rows if r[0]})

    def assigned_in_month(self, budget_id: str, month: str) -> dict[str, int]:
        return self._sum_map(
            """SELECT category_id, SUM(budgeted) FROM monthly_budgets
               WHERE budget_id = ? AND month = ? GROUP BY category_id""",
            (budget_id, month),
        )

    def activity_by_category(self, budget_id: str, through_month: str) -> dict[str, int]:
        """Cumulative spending/activity per category up to and incl. through_month."""
        return self._sum_map(
            """SELECT category_id, SUM(amount) FROM transactions
               WHERE budget_id = ? AND deleted = 0 AND category_id IS NOT NULL
                 AND strftime('%Y-%m-01', date) <= ?
               GROUP BY category_id""",
            (budget_id, through_month),
        )

    def activity_in_month(self, budget_id: str, month: str) -> dict[str, int]:
        return self._sum_map(
            """SELECT category_id, SUM(amount) FROM transactions
               WHERE budget_id = ? AND deleted = 0 AND category_id IS NOT NULL
                 AND strftime('%Y-%m-01', date) = ?
               GROUP BY category_id""",
            (budget_id, month),
        )

    def income_total(self, budget_id: str, through_month: str) -> int:
        """Cumulative income = uncategorized inflows up to and incl. through_month."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT SUM(amount) FROM transactions
                   WHERE budget_id = ? AND deleted = 0 AND category_id IS NULL AND amount > 0
                     AND strftime('%Y-%m-01', date) <= ?""",
                (budget_id, through_month),
            ).fetchone()
            return int(row[0] or 0)

    def income_in_month(self, budget_id: str, month: str) -> int:
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT SUM(amount) FROM transactions
                   WHERE budget_id = ? AND deleted = 0 AND category_id IS NULL AND amount > 0
                     AND strftime('%Y-%m-01', date) = ?""",
                (budget_id, month),
            ).fetchone()
            return int(row[0] or 0)

    def total_assigned(self, budget_id: str, through_month: str) -> int:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT SUM(budgeted) FROM monthly_budgets WHERE budget_id = ? AND month <= ?",
                (budget_id, through_month),
            ).fetchone()
            return int(row[0] or 0)

    def total_assigned_all_months(self, budget_id: str) -> int:
        """Sum of assignments across ALL months (past and future).

        Ready to Assign draws from a single pool of cash, so assigning into a
        *future* month must reduce the current month's RTA too — hence the
        global sum rather than ``month <= ?``. See the engine docstring.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT SUM(budgeted) FROM monthly_budgets WHERE budget_id = ?",
                (budget_id,),
            ).fetchone()
            return int(row[0] or 0)

    def clear_imported_data(self, budget_id: str) -> None:
        """Remove imported transactions, accounts and import history.
        Keeps categories, rules and assignments so the budget structure survives."""
        with self._get_connection() as conn:
            for table in ("transactions", "accounts", "import_batches", "alerts"):
                conn.execute(f"DELETE FROM {table} WHERE budget_id = ?", (budget_id,))
