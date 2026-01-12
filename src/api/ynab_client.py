"""YNAB API client wrapper with rate limiting."""

import time
from collections import deque
from typing import Optional, Any
import ynab
from ynab.rest import ApiException


class RateLimitExceeded(Exception):
    """Raised when YNAB API rate limit would be exceeded."""

    def __init__(self, wait_seconds: float):
        self.wait_seconds = wait_seconds
        super().__init__(f"Rate limit reached. Wait {wait_seconds:.0f} seconds.")


class YNABClient:
    """Wrapper around official YNAB SDK with rate limiting."""

    RATE_LIMIT = 200  # requests per hour
    RATE_WINDOW = 3600  # 1 hour in seconds

    def __init__(self, access_token: str):
        self.configuration = ynab.Configuration(access_token=access_token)
        self._request_times: deque = deque(maxlen=self.RATE_LIMIT)

    def _check_rate_limit(self) -> None:
        """Ensure we don't exceed rate limits."""
        now = time.time()
        # Remove requests older than 1 hour
        while self._request_times and self._request_times[0] < now - self.RATE_WINDOW:
            self._request_times.popleft()

        if len(self._request_times) >= self.RATE_LIMIT:
            wait_time = self._request_times[0] - (now - self.RATE_WINDOW)
            raise RateLimitExceeded(wait_time)

        self._request_times.append(now)

    @property
    def requests_remaining(self) -> int:
        """Get number of requests remaining in current window."""
        now = time.time()
        recent = sum(1 for t in self._request_times if t > now - self.RATE_WINDOW)
        return self.RATE_LIMIT - recent

    def get_budgets(self) -> Any:
        """Fetch all budgets."""
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.BudgetsApi(client)
            response = api.get_budgets()
            return response.data.budgets

    def get_budget(self, budget_id: str, last_knowledge: Optional[int] = None) -> tuple[Any, int]:
        """
        Fetch a single budget with all data.
        Returns (budget_data, server_knowledge).
        """
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.BudgetsApi(client)
            response = api.get_budget(
                budget_id=budget_id,
                last_knowledge_of_server=last_knowledge
            )
            return response.data.budget, response.data.server_knowledge

    def get_accounts(self, budget_id: str, last_knowledge: Optional[int] = None) -> tuple[list, int]:
        """
        Fetch accounts for a budget.
        Returns (accounts, server_knowledge).
        """
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.AccountsApi(client)
            response = api.get_accounts(
                budget_id=budget_id,
                last_knowledge_of_server=last_knowledge
            )
            return response.data.accounts, response.data.server_knowledge

    def get_categories(self, budget_id: str, last_knowledge: Optional[int] = None) -> tuple[list, int]:
        """
        Fetch categories for a budget.
        Returns (category_groups, server_knowledge).
        """
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.CategoriesApi(client)
            response = api.get_categories(
                budget_id=budget_id,
                last_knowledge_of_server=last_knowledge
            )
            return response.data.category_groups, response.data.server_knowledge

    def get_transactions(self, budget_id: str, since_date: Optional[str] = None,
                         last_knowledge: Optional[int] = None) -> tuple[list, int]:
        """
        Fetch transactions for a budget.
        Returns (transactions, server_knowledge).
        """
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.TransactionsApi(client)
            response = api.get_transactions(
                budget_id=budget_id,
                since_date=since_date,
                last_knowledge_of_server=last_knowledge
            )
            return response.data.transactions, response.data.server_knowledge

    def get_scheduled_transactions(self, budget_id: str,
                                    last_knowledge: Optional[int] = None) -> tuple[list, int]:
        """
        Fetch scheduled transactions for a budget.
        Returns (scheduled_transactions, server_knowledge).
        """
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.ScheduledTransactionsApi(client)
            response = api.get_scheduled_transactions(
                budget_id=budget_id,
                last_knowledge_of_server=last_knowledge
            )
            return response.data.scheduled_transactions, response.data.server_knowledge

    def get_months(self, budget_id: str, last_knowledge: Optional[int] = None) -> tuple[list, int]:
        """
        Fetch budget months.
        Returns (months, server_knowledge).
        """
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.MonthsApi(client)
            response = api.get_budget_months(
                budget_id=budget_id,
                last_knowledge_of_server=last_knowledge
            )
            return response.data.months, response.data.server_knowledge

    def get_month(self, budget_id: str, month: str) -> Any:
        """Fetch a specific budget month with category details."""
        self._check_rate_limit()
        with ynab.ApiClient(self.configuration) as client:
            api = ynab.MonthsApi(client)
            response = api.get_budget_month(
                budget_id=budget_id,
                month=month
            )
            return response.data.month

    def test_connection(self) -> bool:
        """Test the API connection by fetching user info."""
        try:
            self._check_rate_limit()
            with ynab.ApiClient(self.configuration) as client:
                api = ynab.UserApi(client)
                api.get_user()
                return True
        except ApiException:
            return False
        except RateLimitExceeded:
            return True  # Connection works, just rate limited
