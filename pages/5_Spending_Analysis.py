"""Spending Analysis page - Deep dive into spending patterns."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from src.utils.formatters import milliunits_to_dollars

st.title("\U0001F4B8 Spending Analysis")

# Get resources from session state
db = st.session_state.get('db')
budget_id = st.session_state.get('budget_id')

if not db or not budget_id:
    st.warning("Please select a budget from the sidebar")
    st.stop()

# Filters
st.sidebar.subheader("Filters")

# Time range selector
time_options = {
    "This Month": 1,
    "Last 3 Months": 3,
    "Last 6 Months": 6,
    "Last 12 Months": 12,
    "All Time": 36
}
selected_time = st.sidebar.selectbox("Time Period", options=list(time_options.keys()), index=1)
months = time_options[selected_time]

# Category filter
categories = db.get_categories(budget_id, include_hidden=False)
category_names = ["All Categories"] + sorted(set(cat['name'] for cat in categories))
selected_category = st.sidebar.selectbox("Category", options=category_names)

# Get spending data
spending_by_cat = db.get_spending_by_category(budget_id, months=months)
monthly_trend = db.get_monthly_spending_trend(budget_id, months=months)

# Summary metrics
st.subheader("Summary")

col1, col2, col3 = st.columns(3)

total_spent = sum(row['total_amount'] for row in spending_by_cat)
total_transactions = sum(row['transaction_count'] for row in spending_by_cat)
avg_transaction = total_spent / total_transactions if total_transactions > 0 else 0

with col1:
    st.metric("Total Spent", f"${milliunits_to_dollars(total_spent):,.2f}")

with col2:
    st.metric("Transactions", f"{total_transactions:,}")

with col3:
    st.metric("Avg Transaction", f"${milliunits_to_dollars(int(avg_transaction)):,.2f}")

st.divider()

# Spending breakdown
st.subheader("Spending Breakdown")

if spending_by_cat:
    # Create dataframe
    df = pd.DataFrame([
        {
            'Category': row['category_name'] or 'Uncategorized',
            'Amount': milliunits_to_dollars(row['total_amount']),
            'Count': row['transaction_count'],
            'Avg': milliunits_to_dollars(row['total_amount'] // row['transaction_count']) if row['transaction_count'] > 0 else 0
        }
        for row in spending_by_cat
    ])

    # Horizontal bar chart
    fig = px.bar(
        df.head(15),
        x='Amount',
        y='Category',
        orientation='h',
        color='Amount',
        color_continuous_scale='Greens'
    )
    fig.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Data table
    with st.expander("View Detailed Data"):
        st.dataframe(
            df.style.format({
                'Amount': '${:,.2f}',
                'Count': '{:,}',
                'Avg': '${:,.2f}'
            }),
            use_container_width=True
        )
else:
    st.info("No spending data available for the selected period.")

st.divider()

# Monthly trend analysis
st.subheader("Monthly Spending Trend")

if monthly_trend:
    df_trend = pd.DataFrame([
        {
            'Month': row['month'],
            'Amount': milliunits_to_dollars(row['total_amount'])
        }
        for row in monthly_trend
    ])

    # Calculate average for reference line
    avg_monthly = df_trend['Amount'].mean()

    fig = go.Figure()

    # Bar chart
    fig.add_trace(go.Bar(
        x=df_trend['Month'],
        y=df_trend['Amount'],
        name='Monthly Spending',
        marker_color='#4CAF50'
    ))

    # Average line
    fig.add_hline(
        y=avg_monthly,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: ${avg_monthly:,.0f}",
        annotation_position="top right"
    )

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Spending ($)",
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Month-over-month change
    if len(df_trend) >= 2:
        current = df_trend.iloc[-1]['Amount']
        previous = df_trend.iloc[-2]['Amount']
        change = ((current - previous) / previous * 100) if previous > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Current Month", f"${current:,.2f}")
        with col2:
            st.metric("Previous Month", f"${previous:,.2f}")
        with col3:
            st.metric("Change", f"{change:+.1f}%", delta=f"${current - previous:,.0f}")

else:
    st.info("No trend data available.")

st.divider()

# Category deep dive
st.subheader("Category Deep Dive")

# Get unique category groups
category_groups = sorted(set(cat['category_group_name'] for cat in categories if cat['category_group_name']))

if category_groups:
    selected_group = st.selectbox("Select Category Group", options=category_groups)

    # Filter categories by group
    group_categories = [cat for cat in categories if cat['category_group_name'] == selected_group]

    if group_categories:
        # Create spending breakdown for this group
        group_spending = []
        for cat in group_categories:
            cat_txns = db.get_category_transactions(budget_id, cat['id'], months=months)
            if cat_txns:
                total = sum(abs(t['amount']) for t in cat_txns if t['amount'] < 0)
                group_spending.append({
                    'Category': cat['name'],
                    'Amount': milliunits_to_dollars(total),
                    'Budgeted': milliunits_to_dollars(cat['budgeted'] or 0),
                    'Transactions': len(cat_txns)
                })

        if group_spending:
            df_group = pd.DataFrame(group_spending)

            # Comparison chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Spent',
                x=df_group['Category'],
                y=df_group['Amount'],
                marker_color='#FF6B6B'
            ))
            fig.add_trace(go.Bar(
                name='Budgeted',
                x=df_group['Category'],
                y=df_group['Budgeted'],
                marker_color='#4ECDC4'
            ))
            fig.update_layout(
                barmode='group',
                xaxis_title="Category",
                yaxis_title="Amount ($)",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                df_group.style.format({
                    'Amount': '${:,.2f}',
                    'Budgeted': '${:,.2f}',
                    'Transactions': '{:,}'
                }),
                use_container_width=True
            )
        else:
            st.info("No spending in this category group for the selected period.")
else:
    st.info("No category groups found.")

st.divider()

# Top payees
st.subheader("Top Payees")

# Get transactions and aggregate by payee
recent_txns = db.get_recent_transactions(budget_id, days=months * 30)
if recent_txns:
    payee_totals = {}
    for txn in recent_txns:
        if txn['amount'] < 0:  # Only outflows
            payee = txn['payee_name'] or 'Unknown'
            if payee not in payee_totals:
                payee_totals[payee] = {'amount': 0, 'count': 0}
            payee_totals[payee]['amount'] += abs(txn['amount'])
            payee_totals[payee]['count'] += 1

    # Sort and display top 10
    sorted_payees = sorted(payee_totals.items(), key=lambda x: x[1]['amount'], reverse=True)[:10]

    df_payees = pd.DataFrame([
        {
            'Payee': payee,
            'Total': milliunits_to_dollars(data['amount']),
            'Transactions': data['count'],
            'Avg': milliunits_to_dollars(data['amount'] // data['count']) if data['count'] > 0 else 0
        }
        for payee, data in sorted_payees
    ])

    col1, col2 = st.columns(2)

    with col1:
        fig = px.pie(
            df_payees,
            values='Total',
            names='Payee',
            hole=0.4
        )
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.dataframe(
            df_payees.style.format({
                'Total': '${:,.2f}',
                'Transactions': '{:,}',
                'Avg': '${:,.2f}'
            }),
            use_container_width=True
        )
else:
    st.info("No transaction data available.")
