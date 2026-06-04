"""Dashboard page - Financial overview."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from src.utils.formatters import milliunits_to_dollars, format_currency, format_change

st.title("\U0001F4CA Financial Dashboard")

# Get resources from session state
db = st.session_state.get('db')
budget_id = st.session_state.get('budget_id')

if not db or not budget_id:
    st.warning("Please select a budget from the sidebar")
    st.stop()

# Get budget info
budget = db.get_budget(budget_id)
if not budget:
    st.warning("Budget not found. Please sync your data.")
    st.stop()

st.caption(f"Budget: **{budget['name']}**")

# Key metrics
st.subheader("This Month at a Glance")

# Get spending data
spending_by_cat = db.get_spending_by_category(budget_id, months=1)
monthly_trend = db.get_monthly_spending_trend(budget_id, months=2)
active_alerts = db.get_active_alerts(budget_id, limit=100)
categories = db.get_current_month_categories(budget_id)

# Calculate metrics
total_spent_this_month = sum(row['total_amount'] for row in spending_by_cat)

# Get previous month spending for comparison
if len(monthly_trend) >= 2:
    this_month = monthly_trend[-1]['total_amount'] if monthly_trend else 0
    prev_month = monthly_trend[-2]['total_amount'] if len(monthly_trend) > 1 else 0
    month_change = format_change(this_month, prev_month)
else:
    month_change = "N/A"

# Budget remaining (sum of positive balances)
total_budgeted = sum(
    (cat['month_budgeted'] or cat['budgeted'] or 0)
    for cat in categories if not cat['hidden']
)
budget_remaining = total_budgeted - total_spent_this_month

# Count categories over budget
over_budget_count = sum(
    1 for cat in categories
    if not cat['hidden'] and
    (cat['month_budgeted'] or cat['budgeted'] or 0) > 0 and
    abs(cat['month_activity'] or cat['activity'] or 0) > (cat['month_budgeted'] or cat['budgeted'] or 0)
)

# Alert counts
critical_alerts = sum(1 for a in active_alerts if a['severity'] == 'critical')
warning_alerts = sum(1 for a in active_alerts if a['severity'] == 'warning')

# Days remaining in month
today = datetime.now()
import calendar
days_in_month = calendar.monthrange(today.year, today.month)[1]
days_remaining = days_in_month - today.day

# Display metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Spent",
        f"${milliunits_to_dollars(total_spent_this_month):,.2f}",
        delta=month_change,
        delta_color="inverse"
    )

with col2:
    st.metric(
        "Budget Remaining",
        f"${milliunits_to_dollars(budget_remaining):,.2f}",
        delta=f"{days_remaining} days left"
    )

with col3:
    alert_count = len(active_alerts)
    st.metric(
        "Active Alerts",
        alert_count,
        delta=f"{critical_alerts} critical" if critical_alerts > 0 else None,
        delta_color="inverse"
    )

with col4:
    st.metric(
        "Over Budget",
        over_budget_count,
        delta=f"{over_budget_count} categories" if over_budget_count > 0 else "All good!",
        delta_color="inverse" if over_budget_count > 0 else "normal"
    )

st.divider()

# Charts row
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Spending by Category")

    if spending_by_cat:
        # Prepare data for pie chart
        df = pd.DataFrame([
            {
                'category': row['category_name'] or 'Uncategorized',
                'amount': milliunits_to_dollars(row['total_amount'])
            }
            for row in spending_by_cat[:10]  # Top 10 categories
        ])

        fig = px.pie(
            df,
            values='amount',
            names='category',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No spending data available for this month.")

with chart_col2:
    st.subheader("Monthly Spending Trend")

    # Get 12-month trend
    full_trend = db.get_monthly_spending_trend(budget_id, months=12)

    if full_trend:
        df = pd.DataFrame([
            {
                'month': row['month'],
                'amount': milliunits_to_dollars(row['total_amount'])
            }
            for row in full_trend
        ])

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['month'],
            y=df['amount'],
            marker_color='#4CAF50'
        ))
        fig.update_layout(
            xaxis_title="Month",
            yaxis_title="Spending ($)",
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trend data available.")

st.divider()

# Recent transactions and alerts
txn_col, alert_col = st.columns([2, 1])

with txn_col:
    st.subheader("Recent Transactions")

    recent_txns = db.get_recent_transactions(budget_id, days=14)[:10]

    if recent_txns:
        for txn in recent_txns:
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    payee = txn['payee_name'] or "Unknown"
                    category = txn['category_name'] or "Uncategorized"
                    st.markdown(f"**{payee}**")
                    st.caption(f"{category} | {txn['date']}")
                with c2:
                    amount = milliunits_to_dollars(txn['amount'])
                    if txn['amount'] < 0:
                        st.markdown(f":red[-${abs(amount):,.2f}]")
                    else:
                        st.markdown(f":green[+${amount:,.2f}]")
                with c3:
                    if txn['memo']:
                        st.caption(txn['memo'][:20] + "..." if len(txn['memo']) > 20 else txn['memo'])
                st.divider()
    else:
        st.info("No recent transactions found. Try syncing your data.")

with alert_col:
    st.subheader("Active Alerts")

    display_alerts = active_alerts[:5]

    if display_alerts:
        for alert in display_alerts:
            severity_icon = {
                "critical": "\U0001F534",
                "warning": "\U0001F7E0",
                "info": "\U0001F535"
            }.get(alert['severity'], "\u26AA")

            st.markdown(f"{severity_icon} **{alert['title']}**")
            st.caption(alert['description'][:100] + "..." if len(alert['description']) > 100 else alert['description'])
            st.divider()

        if len(active_alerts) > 5:
            st.caption(f"+ {len(active_alerts) - 5} more alerts")
    else:
        st.success("No active alerts!")

# Category budget status
st.divider()
st.subheader("Category Budget Status")

# Filter to categories with budgets
budgeted_cats = [
    cat for cat in categories
    if not cat['hidden'] and (cat['month_budgeted'] or cat['budgeted'] or 0) > 0
]

if budgeted_cats:
    # Create progress bars for each category
    for cat in sorted(budgeted_cats, key=lambda x: abs(x['month_activity'] or x['activity'] or 0), reverse=True)[:10]:
        budgeted = cat['month_budgeted'] or cat['budgeted'] or 0
        spent = abs(cat['month_activity'] or cat['activity'] or 0)
        remaining = budgeted - spent
        ratio = spent / budgeted if budgeted > 0 else 0

        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            group = cat['category_group_name'] or ""
            st.markdown(f"**{cat['name']}**")
            st.caption(group)

        with col2:
            # Color based on ratio
            if ratio > 1.0:
                color = "red"
            elif ratio > 0.9:
                color = "orange"
            else:
                color = "green"

            st.progress(min(ratio, 1.0), text=f"{ratio:.0%}")

        with col3:
            spent_str = f"${milliunits_to_dollars(spent):,.0f}"
            budget_str = f"${milliunits_to_dollars(budgeted):,.0f}"
            st.caption(f"{spent_str} / {budget_str}")

else:
    st.info("No categories with budgets found.")
