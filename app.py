"""BUD - a local-first, zero-based budgeting app. Import bank statements,
give every dollar a job. No bank connection, no third parties: all data
stays in a local SQLite database."""

import streamlit as st

from src.cache.database import Database, LOCAL_BUDGET_ID
from src.budget.engine import BudgetEngine
from src.utils.formatters import format_currency

st.set_page_config(
    page_title="BUD - Budget",
    page_icon="\U0001F4B0",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_database():
    """Singleton database instance (creates + seeds on first run)."""
    return Database()


db = get_database()

# Single local budget — keep the budget_id plumbing for a possible multi-budget future.
st.session_state.db = db
st.session_state.budget_id = LOCAL_BUDGET_ID

# Pages
budget_page = st.Page("pages/0_Budget.py", title="Budget", icon="\U0001F4B5", default=True)
import_page = st.Page("pages/1_Import.py", title="Import", icon="\U0001F4E5")
transactions_page = st.Page("pages/2_Transactions.py", title="Transactions", icon="\U0001F9FE")
categories_page = st.Page("pages/3_Categories.py", title="Categories", icon="\U0001F3F7️")
dashboard = st.Page("pages/4_Dashboard.py", title="Dashboard", icon="\U0001F4CA")
spending = st.Page("pages/5_Spending_Analysis.py", title="Spending Analysis", icon="\U0001F4B8")
alerts_page = st.Page("pages/6_Alerts.py", title="Alerts", icon="\U0001F514")
settings = st.Page("pages/7_Settings.py", title="Settings", icon="⚙️")

pg = st.navigation({
    "Budget": [budget_page, import_page, transactions_page, categories_page],
    "Insights": [dashboard, spending, alerts_page],
    "Configuration": [settings],
})

# Sidebar: identity, accounts, and the things that need attention.
with st.sidebar:
    st.title("\U0001F4B0 BUD")

    accounts = db.get_accounts(LOCAL_BUDGET_ID)
    if not accounts:
        st.info("No accounts yet.\n\nHead to **Import** to upload a bank statement (OFX/QFX).")
    else:
        total = sum(a["balance"] or 0 for a in accounts)
        st.metric("Total balance", format_currency(total))
        with st.expander(f"{len(accounts)} account(s)", expanded=False):
            for a in accounts:
                st.caption(f"{a['name']} — {format_currency(a['balance'] or 0)}")

    st.divider()

    # Things needing attention: Ready to Assign + uncategorized.
    state = BudgetEngine(db).get_state()
    rta = state.ready_to_assign
    if rta > 0:
        st.warning(f"\U0001F4B0 {format_currency(rta)} ready to assign")
    elif rta < 0:
        st.error(f"⚠️ {format_currency(rta)} over-assigned")
    else:
        st.success("✅ Every dollar has a job")

    uncategorized = db.count_uncategorized(LOCAL_BUDGET_ID)
    if uncategorized:
        st.caption(f"\U0001F9FE {uncategorized} transaction(s) need a category")

    active_alerts = db.get_active_alerts(LOCAL_BUDGET_ID, limit=100)
    if active_alerts:
        critical = sum(1 for a in active_alerts if a["severity"] == "critical")
        if critical:
            st.error(f"\U0001F534 {critical} critical alert(s)")

pg.run()
