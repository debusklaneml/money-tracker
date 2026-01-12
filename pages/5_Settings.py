"""Settings page - Configure application settings."""

import streamlit as st
from datetime import datetime

from src.cache.sync import SyncManager
from src.api.ynab_client import RateLimitExceeded

st.title("\u2699\ufe0f Settings")

# Get resources from session state
db = st.session_state.get('db')
client = st.session_state.get('client')
budget_id = st.session_state.get('budget_id')

if not db or not client:
    st.warning("Application not properly initialized")
    st.stop()

# API Status
st.subheader("YNAB API Status")

col1, col2, col3 = st.columns(3)

with col1:
    if client.test_connection():
        st.success("\u2705 Connected")
    else:
        st.error("\u274c Connection failed")

with col2:
    remaining = client.requests_remaining
    st.metric("API Requests Remaining", f"{remaining}/200")

with col3:
    st.progress(remaining / 200)

st.divider()

# Sync Management
st.subheader("Data Sync")

if budget_id:
    sync_manager = SyncManager(db, client)
    status = sync_manager.get_sync_status(budget_id)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Last Sync**")
        if status['last_sync']:
            st.write(status['last_sync'])
        else:
            st.write("Never synced")

    with col2:
        st.markdown("**Sync Knowledge**")
        for endpoint, knowledge in status['knowledge'].items():
            if knowledge:
                st.caption(f"{endpoint}: {knowledge}")

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Quick Sync", help="Sync only changed data"):
            try:
                with st.spinner("Syncing..."):
                    stats = sync_manager.sync_budget(budget_id)
                    sync_manager.sync_month_budgets(budget_id)
                st.success(f"Synced {stats['transactions']} transactions")
            except RateLimitExceeded as e:
                st.warning(f"Rate limited: {e}")
            except Exception as e:
                st.error(f"Sync failed: {e}")

    with col2:
        if st.button("Full Sync", help="Force complete data refresh"):
            try:
                with st.spinner("Full sync in progress..."):
                    stats = sync_manager.sync_budget(budget_id, force_full=True)
                    sync_manager.sync_month_budgets(budget_id)
                st.success("Full sync complete!")
            except Exception as e:
                st.error(f"Full sync failed: {e}")

    with col3:
        if st.button("Sync All Budgets"):
            try:
                with st.spinner("Syncing all budgets..."):
                    budget_ids = sync_manager.sync_budgets()
                st.success(f"Synced {len(budget_ids)} budget(s)")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

else:
    st.info("Select a budget to view sync options")

st.divider()

# Alert Thresholds
st.subheader("Alert Thresholds")

st.markdown("""
Alert thresholds can be configured in your `.streamlit/secrets.toml` file:

```toml
[alert_thresholds]
unusual_spending_warning = 2.5    # Modified Z-Score for warning
unusual_spending_critical = 3.5   # Modified Z-Score for critical
budget_approaching = 0.90         # Budget % to trigger warning
recurring_days_warning = 3        # Days overdue for warning
recurring_days_critical = 7       # Days overdue for critical
```
""")

# Display current thresholds (from config)
try:
    from src.utils.config import AlertThresholds
    thresholds = AlertThresholds()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Current Thresholds**")
        st.write(f"Unusual Spending Warning: {thresholds.unusual_spending_warning}")
        st.write(f"Unusual Spending Critical: {thresholds.unusual_spending_critical}")
        st.write(f"Budget Approaching: {thresholds.budget_approaching:.0%}")

    with col2:
        st.write(f"Recurring Days Warning: {thresholds.recurring_days_warning}")
        st.write(f"Recurring Days Critical: {thresholds.recurring_days_critical}")
        st.write(f"Amount Tolerance: {thresholds.recurring_amount_tolerance_percent}%")

except Exception:
    st.info("Using default thresholds")

st.divider()

# Database Info
st.subheader("Database Information")

if budget_id:
    # Get counts
    accounts = db.get_accounts(budget_id)
    categories = db.get_categories(budget_id, include_hidden=True)
    transactions = db.get_transactions(budget_id, limit=1000000)  # Get count
    scheduled = db.get_scheduled_transactions(budget_id)
    alerts = db.get_alerts(budget_id, include_dismissed=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Accounts", len(accounts))
        st.metric("Categories", len(categories))

    with col2:
        st.metric("Transactions", len(transactions))
        st.metric("Scheduled", len(scheduled))

    with col3:
        st.metric("Alerts", len(alerts))
        st.metric("Active Alerts", len([a for a in alerts if not a['dismissed']]))

    st.divider()

    # Database path
    st.caption(f"Database location: `{db.db_path}`")

st.divider()

# About
st.subheader("About BUD")

st.markdown("""
**BUD - Budget Dashboard** is a financial tracking application that connects to your YNAB account
to provide insights, alerts, and analysis of your spending.

### Features
- \U0001F4CA **Dashboard**: Overview of spending and budget status
- \U0001F4B8 **Spending Analysis**: Deep dive into spending patterns
- \U0001F514 **Alerts**: Unusual spending detection, budget monitoring
- \U0001F501 **Recurring**: Track scheduled transactions

### Data Privacy
- All data is stored locally on your computer
- No data is sent to third parties
- API communication is directly with YNAB

### Rate Limits
YNAB API allows 200 requests per hour. BUD uses delta sync to minimize API calls.

---

Built with Streamlit and the YNAB API.
""")

# Version info
st.caption("Version 0.1.0")
