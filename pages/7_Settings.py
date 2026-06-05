"""Settings page - data management and configuration."""

import streamlit as st

from src.utils.formatters import format_currency
from src.utils.config import load_alert_thresholds

st.title("⚙️ Settings")

db = st.session_state.get("db")
budget_id = st.session_state.get("budget_id")
if not db or not budget_id:
    st.warning("App not initialized.")
    st.stop()

# --- Data overview ----------------------------------------------------------
st.subheader("Your Data")
accounts = db.get_accounts(budget_id)
categories = db.get_categories(budget_id, include_hidden=True)
transactions = db.get_transactions(budget_id, limit=1_000_000)
batches = db.get_import_batches(budget_id)
rules = db.get_rules(budget_id)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Accounts", len(accounts))
    st.metric("Categories", len(categories))
with c2:
    st.metric("Transactions", len(transactions))
    st.metric("Uncategorized", db.count_uncategorized(budget_id))
with c3:
    st.metric("Import batches", len(batches))
    st.metric("Rules", len(rules))

if accounts:
    st.caption("Account balances")
    for a in accounts:
        st.write(f"- {a['name']}: {format_currency(a['balance'] or 0)}")

st.divider()

# --- Alert thresholds -------------------------------------------------------
st.subheader("Alert Thresholds")
st.caption("Configure in `.streamlit/secrets.toml` under `[alert_thresholds]`.")
t = load_alert_thresholds()
col1, col2 = st.columns(2)
with col1:
    st.write(f"Unusual spending (warning): **{t.unusual_spending_warning}**")
    st.write(f"Unusual spending (critical): **{t.unusual_spending_critical}**")
with col2:
    st.write(f"Budget approaching: **{t.budget_approaching:.0%}**")

st.divider()

# --- Data management --------------------------------------------------------
st.subheader("Data Management")
st.caption(f"Database location: `{db.db_path}`")

with st.expander("⚠️ Danger zone"):
    st.markdown(
        "Remove all imported **transactions, accounts and import history**. "
        "Your categories, rules and assignments are kept."
    )
    confirm = st.checkbox("I understand this can't be undone")
    if st.button("Clear imported data", type="primary", disabled=not confirm):
        db.clear_imported_data(budget_id)
        st.success("Imported data cleared.")
        st.rerun()

st.divider()

# --- About ------------------------------------------------------------------
st.subheader("About BUD")
st.markdown("""
**BUD** is a local-first, zero-based budgeting app. You import OFX/QFX bank
statements and give every dollar a job — no bank connection, no third parties.
All data lives in a local SQLite database on your machine.

- \U0001F4B5 **Budget** — assign every dollar, cover overspending
- \U0001F4E5 **Import** — upload OFX/QFX statements
- \U0001F9FE **Transactions** — categorize and build auto-rules
- \U0001F3F7️ **Categories** — manage your envelopes
- \U0001F4CA **Insights** — dashboard, spending analysis, alerts
""")
st.caption("Version 0.2.0")
