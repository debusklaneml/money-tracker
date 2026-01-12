"""SQLite database manager for local data caching."""

import sqlite3
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

-- Sync metadata for delta requests
CREATE TABLE IF NOT EXISTS sync_metadata (
    budget_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    last_knowledge_of_server INTEGER,
    last_sync_at TIMESTAMP,
    PRIMARY KEY (budget_id, endpoint)
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

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_budget_date ON transactions(budget_id, date);
CREATE INDEX IF NOT EXISTS idx_transactions_payee ON transactions(payee_id);
CREATE INDEX IF NOT EXISTS idx_alerts_budget ON alerts(budget_id, dismissed, created_at);
CREATE INDEX IF NOT EXISTS idx_categories_budget ON categories(budget_id);
CREATE INDEX IF NOT EXISTS idx_monthly_budgets_budget_month ON monthly_budgets(budget_id, month);
"""


class Database:
    """SQLite database manager with connection pooling."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".bud" / "cache.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)

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
