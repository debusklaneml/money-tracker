"""Sync manager for YNAB data with delta sync support."""

from datetime import datetime
from typing import Optional
import logging

from src.api.ynab_client import YNABClient, RateLimitExceeded
from src.cache.database import Database

logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Raised when sync fails."""
    pass


class SyncManager:
    """Manages synchronization between YNAB API and local database."""

    ENDPOINTS = ['accounts', 'categories', 'transactions', 'scheduled_transactions']

    def __init__(self, db: Database, client: YNABClient):
        self.db = db
        self.client = client

    def sync_budgets(self) -> list[str]:
        """
        Sync all budgets from YNAB.
        Returns list of budget IDs.
        """
        try:
            budgets = self.client.get_budgets()
            budget_ids = []

            for budget in budgets:
                self.db.upsert_budget(
                    budget_id=budget.id,
                    name=budget.name,
                    last_modified_on=str(budget.last_modified_on) if budget.last_modified_on else None,
                    first_month=budget.first_month,
                    last_month=budget.last_month,
                    currency_format=str(budget.currency_format) if budget.currency_format else None
                )
                budget_ids.append(budget.id)
                logger.info(f"Synced budget: {budget.name}")

            return budget_ids
        except RateLimitExceeded as e:
            raise SyncError(f"Rate limit exceeded: {e}")
        except Exception as e:
            raise SyncError(f"Failed to sync budgets: {e}")

    def sync_budget(self, budget_id: str, force_full: bool = False) -> dict:
        """
        Sync all data for a specific budget.
        Uses delta sync when possible.
        Returns dict with sync statistics.
        """
        stats = {
            'accounts': 0,
            'categories': 0,
            'transactions': 0,
            'scheduled_transactions': 0,
            'errors': []
        }

        # Sync accounts
        try:
            count = self._sync_accounts(budget_id, force_full)
            stats['accounts'] = count
        except Exception as e:
            stats['errors'].append(f"Accounts: {e}")
            logger.error(f"Error syncing accounts: {e}")

        # Sync categories
        try:
            count = self._sync_categories(budget_id, force_full)
            stats['categories'] = count
        except Exception as e:
            stats['errors'].append(f"Categories: {e}")
            logger.error(f"Error syncing categories: {e}")

        # Sync transactions
        try:
            count = self._sync_transactions(budget_id, force_full)
            stats['transactions'] = count
        except Exception as e:
            stats['errors'].append(f"Transactions: {e}")
            logger.error(f"Error syncing transactions: {e}")

        # Sync scheduled transactions
        try:
            count = self._sync_scheduled_transactions(budget_id, force_full)
            stats['scheduled_transactions'] = count
        except Exception as e:
            stats['errors'].append(f"Scheduled transactions: {e}")
            logger.error(f"Error syncing scheduled transactions: {e}")

        return stats

    def _sync_accounts(self, budget_id: str, force_full: bool = False) -> int:
        """Sync accounts for a budget."""
        last_knowledge = None if force_full else self.db.get_sync_knowledge(budget_id, 'accounts')

        accounts, server_knowledge = self.client.get_accounts(budget_id, last_knowledge)

        for account in accounts:
            self.db.upsert_account(
                account_id=account.id,
                budget_id=budget_id,
                name=account.name,
                account_type=account.type,
                on_budget=account.on_budget,
                closed=account.closed,
                balance=account.balance,
                cleared_balance=account.cleared_balance,
                uncleared_balance=account.uncleared_balance
            )

        self.db.update_sync_knowledge(budget_id, 'accounts', server_knowledge)
        logger.info(f"Synced {len(accounts)} accounts")
        return len(accounts)

    def _sync_categories(self, budget_id: str, force_full: bool = False) -> int:
        """Sync categories for a budget."""
        last_knowledge = None if force_full else self.db.get_sync_knowledge(budget_id, 'categories')

        category_groups, server_knowledge = self.client.get_categories(budget_id, last_knowledge)

        count = 0
        for group in category_groups:
            for category in group.categories:
                self.db.upsert_category(
                    category_id=category.id,
                    budget_id=budget_id,
                    category_group_id=group.id,
                    category_group_name=group.name,
                    name=category.name,
                    hidden=category.hidden,
                    budgeted=category.budgeted,
                    activity=category.activity,
                    balance=category.balance,
                    goal_type=category.goal_type,
                    goal_target=category.goal_target,
                    goal_target_month=category.goal_target_month
                )
                count += 1

        self.db.update_sync_knowledge(budget_id, 'categories', server_knowledge)
        logger.info(f"Synced {count} categories")
        return count

    def _sync_transactions(self, budget_id: str, force_full: bool = False) -> int:
        """Sync transactions for a budget."""
        last_knowledge = None if force_full else self.db.get_sync_knowledge(budget_id, 'transactions')

        transactions, server_knowledge = self.client.get_transactions(
            budget_id,
            last_knowledge=last_knowledge
        )

        for txn in transactions:
            self.db.upsert_transaction(
                txn_id=txn.id,
                budget_id=budget_id,
                account_id=txn.account_id,
                account_name=txn.account_name,
                txn_date=str(txn.date),
                amount=txn.amount,
                memo=txn.memo,
                cleared=txn.cleared,
                approved=txn.approved,
                flag_color=txn.flag_color,
                payee_id=txn.payee_id,
                payee_name=txn.payee_name,
                category_id=txn.category_id,
                category_name=txn.category_name,
                transfer_account_id=txn.transfer_account_id,
                transfer_transaction_id=txn.transfer_transaction_id,
                import_id=txn.import_id,
                deleted=txn.deleted
            )

        self.db.update_sync_knowledge(budget_id, 'transactions', server_knowledge)
        logger.info(f"Synced {len(transactions)} transactions")
        return len(transactions)

    def _sync_scheduled_transactions(self, budget_id: str, force_full: bool = False) -> int:
        """Sync scheduled transactions for a budget."""
        last_knowledge = None if force_full else self.db.get_sync_knowledge(budget_id, 'scheduled_transactions')

        scheduled, server_knowledge = self.client.get_scheduled_transactions(budget_id, last_knowledge)

        for sched in scheduled:
            self.db.upsert_scheduled_transaction(
                sched_id=sched.id,
                budget_id=budget_id,
                account_id=sched.account_id,
                account_name=sched.account_name,
                date_first=str(sched.date_first),
                date_next=str(sched.date_next),
                frequency=sched.frequency,
                amount=sched.amount,
                memo=sched.memo,
                payee_id=sched.payee_id,
                payee_name=sched.payee_name,
                category_id=sched.category_id,
                category_name=sched.category_name,
                deleted=sched.deleted
            )

        self.db.update_sync_knowledge(budget_id, 'scheduled_transactions', server_knowledge)
        logger.info(f"Synced {len(scheduled)} scheduled transactions")
        return len(scheduled)

    def sync_month_budgets(self, budget_id: str, month: Optional[str] = None) -> int:
        """
        Sync monthly budget data.
        If month is None, syncs current month.
        """
        if month is None:
            month = datetime.now().strftime('%Y-%m-01')

        try:
            month_data = self.client.get_month(budget_id, month)
            count = 0

            for category in month_data.categories:
                self.db.upsert_monthly_budget(
                    budget_id=budget_id,
                    month=month,
                    category_id=category.id,
                    budgeted=category.budgeted,
                    activity=category.activity,
                    balance=category.balance
                )
                count += 1

            logger.info(f"Synced {count} monthly budget entries for {month}")
            return count
        except Exception as e:
            raise SyncError(f"Failed to sync month {month}: {e}")

    def get_sync_status(self, budget_id: str) -> dict:
        """Get sync status for a budget."""
        last_sync = self.db.get_last_sync(budget_id)
        knowledge = {}

        for endpoint in self.ENDPOINTS:
            k = self.db.get_sync_knowledge(budget_id, endpoint)
            knowledge[endpoint] = k

        return {
            'budget_id': budget_id,
            'last_sync': last_sync.isoformat() if last_sync else None,
            'knowledge': knowledge,
            'requests_remaining': self.client.requests_remaining
        }
