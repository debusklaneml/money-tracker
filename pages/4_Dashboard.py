"""Dashboard - financial overview built on the local budgeting engine."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.budget.engine import BudgetEngine, current_month
from src.utils.formatters import milliunits_to_dollars, format_currency, format_month

st.title("\U0001F4CA Dashboard")

db = st.session_state.get("db")
budget_id = st.session_state.get("budget_id")
if not db or not budget_id:
    st.warning("App not initialized.")
    st.stop()

engine = BudgetEngine(db, budget_id)
month = current_month()
state = engine.get_state(month)
accounts = db.get_accounts(budget_id)

st.caption(f"{format_month(month)}")

# --- Top metrics (all calendar-month correct via the engine) ---------------
total_balance = sum(a["balance"] or 0 for a in accounts)
spent_this_month = -sum(c.activity for c in state.categories if c.activity < 0)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Balance", format_currency(total_balance))
m2.metric("Ready to Assign", format_currency(state.ready_to_assign))
m3.metric("Spent This Month", format_currency(spent_this_month))
m4.metric("Overspent Envelopes", len(state.overspent),
          delta=None if not state.overspent else "needs attention", delta_color="inverse")

if not accounts:
    st.info("No data yet. Go to **Import** to upload a bank statement.")
    st.stop()

st.divider()

# --- Charts ----------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Spending by Category (this month)")
    spend = sorted(
        [(c.name, -c.activity) for c in state.categories if c.activity < 0],
        key=lambda x: x[1], reverse=True,
    )
    if spend:
        df = pd.DataFrame(
            [{"category": n, "amount": float(milliunits_to_dollars(a))} for n, a in spend[:10]]
        )
        fig = px.pie(df, values="amount", names="category", hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Set3)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No categorized spending this month yet.")

with right:
    st.subheader("Monthly Spending Trend")
    trend = db.get_monthly_spending_trend(budget_id, months=12)
    if trend:
        df = pd.DataFrame([
            {"month": r["month"], "amount": float(milliunits_to_dollars(r["total_amount"]))}
            for r in trend
        ])
        fig = go.Figure(go.Bar(x=df["month"], y=df["amount"], marker_color="#4CAF50"))
        fig.update_layout(xaxis_title="Month", yaxis_title="Spending ($)",
                          margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trend data yet.")

st.divider()

# --- Recent transactions + envelope status ---------------------------------
txn_col, env_col = st.columns([2, 1])

with txn_col:
    st.subheader("Recent Transactions")
    recent = db.get_transactions(budget_id, limit=12)
    if recent:
        for t in recent:
            a, b = st.columns([3, 1])
            with a:
                st.markdown(f"**{t['payee_name'] or 'Unknown'}**")
                st.caption(f"{t['category_name'] or 'Uncategorized'} · {t['date']}")
            with b:
                amt = milliunits_to_dollars(t["amount"])
                st.markdown(f":red[-${abs(amt):,.2f}]" if t["amount"] < 0 else f":green[+${amt:,.2f}]")
            st.divider()
    else:
        st.info("No transactions yet.")

with env_col:
    st.subheader("Envelopes Needing Attention")
    shown = False
    for c in sorted(state.categories, key=lambda c: c.available):
        if c.available < 0:
            st.markdown(f"\U0001F534 **{c.name}** — {format_currency(c.available)}")
            shown = True
    if not shown:
        st.success("No overspent envelopes \U0001F389")
