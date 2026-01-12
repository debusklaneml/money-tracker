"""BUD - Budget Dashboard: Main Streamlit application."""

import streamlit as st

from src.api.ynab_client import YNABClient, RateLimitExceeded
from src.cache.database import Database
from src.cache.sync import SyncManager, SyncError
from src.utils.config import get_token_from_secrets, validate_token

# Page configuration
st.set_page_config(
    page_title="BUD - Budget Dashboard",
    page_icon="\U0001F4B0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.budget_id = None
    st.session_state.budgets = []


@st.cache_resource
def get_database():
    """Get singleton database instance."""
    return Database()


@st.cache_resource
def get_ynab_client(token: str):
    """Get singleton YNAB client instance."""
    return YNABClient(token)


def init_app():
    """Initialize the application."""
    token = get_token_from_secrets()

    if not token or not validate_token(token):
        return None, None

    db = get_database()
    client = get_ynab_client(token)
    return db, client


# Initialize
db, client = init_app()

# Check for token
if client is None:
    st.title("\U0001F4B0 BUD - Budget Dashboard")
    st.error("YNAB Access Token not configured.")
    st.markdown("""
    ### Setup Instructions

    1. Create the secrets file: `.streamlit/secrets.toml`
    2. Add your YNAB Personal Access Token:

    ```toml
    YNAB_ACCESS_TOKEN = "your-token-here"
    ```

    3. Get your token from: **YNAB Settings > Developer Settings > Personal Access Tokens**
    4. Restart the application

    See `.streamlit/secrets.toml.example` for a template.
    """)
    st.stop()

# Test connection on first run
if not st.session_state.initialized:
    with st.spinner("Connecting to YNAB..."):
        if client.test_connection():
            st.session_state.initialized = True
        else:
            st.error("Failed to connect to YNAB. Please check your access token.")
            st.stop()

# Define pages
dashboard = st.Page("pages/1_Dashboard.py", title="Dashboard", icon="\U0001F4CA", default=True)
spending = st.Page("pages/2_Spending_Analysis.py", title="Spending Analysis", icon="\U0001F4B8")
alerts_page = st.Page("pages/3_Alerts.py", title="Alerts", icon="\U0001F514")
recurring = st.Page("pages/4_Recurring.py", title="Recurring", icon="\U0001F501")
settings = st.Page("pages/5_Settings.py", title="Settings", icon="\u2699\ufe0f")

pg = st.navigation({
    "Overview": [dashboard],
    "Analysis": [spending, recurring],
    "Monitoring": [alerts_page],
    "Configuration": [settings]
})

# Sidebar
with st.sidebar:
    st.title("\U0001F4B0 BUD")

    # Budget selector
    budgets = db.get_budgets()

    if not budgets:
        st.info("No budgets loaded yet.")
        if st.button("Load Budgets from YNAB"):
            try:
                with st.spinner("Fetching budgets..."):
                    sync = SyncManager(db, client)
                    budget_ids = sync.sync_budgets()
                    st.success(f"Loaded {len(budget_ids)} budget(s)")
                    st.rerun()
            except SyncError as e:
                st.error(f"Sync failed: {e}")
            except RateLimitExceeded as e:
                st.warning(f"Rate limit: {e}")
    else:
        budget_names = {b['id']: b['name'] for b in budgets}
        budget_list = list(budget_names.keys())

        # Set default budget
        if st.session_state.budget_id is None and budget_list:
            st.session_state.budget_id = budget_list[0]

        selected = st.selectbox(
            "Select Budget",
            options=budget_list,
            format_func=lambda x: budget_names.get(x, x),
            key="budget_selector",
            index=budget_list.index(st.session_state.budget_id) if st.session_state.budget_id in budget_list else 0
        )
        st.session_state.budget_id = selected

        st.divider()

        # Sync status
        last_sync = db.get_last_sync(selected)
        if last_sync:
            st.caption(f"Last sync: {last_sync.strftime('%Y-%m-%d %H:%M')}")
        else:
            st.caption("Never synced")

        # API rate limit display
        remaining = client.requests_remaining
        st.progress(remaining / 200, text=f"API: {remaining}/200 requests")

        # Sync button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sync", disabled=remaining < 10, help="Sync data from YNAB"):
                try:
                    sync = SyncManager(db, client)
                    with st.spinner("Syncing..."):
                        stats = sync.sync_budget(selected)
                        # Also sync current month budgets
                        sync.sync_month_budgets(selected)

                    if stats['errors']:
                        st.warning(f"Sync completed with errors: {stats['errors']}")
                    else:
                        st.success(
                            f"Synced: {stats['transactions']} txns, "
                            f"{stats['categories']} cats"
                        )
                    st.rerun()
                except SyncError as e:
                    st.error(f"Sync failed: {e}")
                except RateLimitExceeded as e:
                    st.warning(f"Rate limit: {e}")

        with col2:
            if st.button("Full Sync", disabled=remaining < 20, help="Force full data refresh"):
                try:
                    sync = SyncManager(db, client)
                    with st.spinner("Full sync in progress..."):
                        stats = sync.sync_budget(selected, force_full=True)
                        sync.sync_month_budgets(selected)
                    st.success("Full sync complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Full sync failed: {e}")

    st.divider()

    # Quick stats
    if st.session_state.budget_id:
        active_alerts = db.get_active_alerts(st.session_state.budget_id, limit=5)
        if active_alerts:
            critical = sum(1 for a in active_alerts if a['severity'] == 'critical')
            warning = sum(1 for a in active_alerts if a['severity'] == 'warning')
            if critical:
                st.error(f"\U0001F534 {critical} critical alert(s)")
            if warning:
                st.warning(f"\U0001F7E0 {warning} warning(s)")

# Store db and client in session for pages
st.session_state.db = db
st.session_state.client = client

# Run the selected page
pg.run()
