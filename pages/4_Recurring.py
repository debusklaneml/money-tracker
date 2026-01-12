"""Recurring transactions page - View and monitor scheduled transactions."""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

from src.utils.formatters import milliunits_to_dollars

st.title("\U0001F501 Recurring Transactions")

# Get resources from session state
db = st.session_state.get('db')
budget_id = st.session_state.get('budget_id')

if not db or not budget_id:
    st.warning("Please select a budget from the sidebar")
    st.stop()

# Get scheduled transactions
scheduled = db.get_scheduled_transactions(budget_id)

if not scheduled:
    st.info("No recurring transactions found. Try syncing your data from YNAB.")
    st.stop()

# Summary
st.subheader("Summary")

total_monthly = 0
upcoming_count = 0
today = date.today()

for sched in scheduled:
    # Estimate monthly amount based on frequency
    amount = abs(sched['amount'])
    freq = sched['frequency'] or 'monthly'

    if freq == 'weekly':
        monthly = amount * 4.33
    elif freq == 'everyOtherWeek':
        monthly = amount * 2.17
    elif freq == 'twiceAMonth':
        monthly = amount * 2
    elif freq == 'every4Weeks':
        monthly = amount * (52 / 12 / 4)
    elif freq == 'monthly':
        monthly = amount
    elif freq == 'everyOtherMonth':
        monthly = amount / 2
    elif freq == 'every3Months':
        monthly = amount / 3
    elif freq == 'every4Months':
        monthly = amount / 4
    elif freq == 'twiceAYear':
        monthly = amount / 6
    elif freq == 'yearly':
        monthly = amount / 12
    else:
        monthly = amount  # Default to monthly

    total_monthly += monthly

    # Check if upcoming (within 7 days)
    if isinstance(sched['date_next'], str):
        next_date = date.fromisoformat(sched['date_next'])
    else:
        next_date = sched['date_next']

    if next_date and (next_date - today).days <= 7:
        upcoming_count += 1

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Recurring", len(scheduled))

with col2:
    st.metric("Est. Monthly Total", f"${milliunits_to_dollars(int(total_monthly)):,.2f}")

with col3:
    st.metric("Due This Week", upcoming_count)

st.divider()

# Upcoming transactions
st.subheader("Upcoming Transactions")

# Filter for upcoming (next 30 days)
upcoming = []
for sched in scheduled:
    if isinstance(sched['date_next'], str):
        next_date = date.fromisoformat(sched['date_next'])
    else:
        next_date = sched['date_next']

    if next_date:
        days_until = (next_date - today).days
        if days_until <= 30:
            upcoming.append({
                'sched': sched,
                'next_date': next_date,
                'days_until': days_until
            })

# Sort by date
upcoming.sort(key=lambda x: x['next_date'])

if upcoming:
    for item in upcoming:
        sched = item['sched']
        days_until = item['days_until']

        # Status indicator
        if days_until < 0:
            status = "\U0001F534 Overdue"
            status_color = "red"
        elif days_until == 0:
            status = "\U0001F7E0 Due today"
            status_color = "orange"
        elif days_until <= 3:
            status = "\U0001F7E1 Due soon"
            status_color = "yellow"
        else:
            status = f"\U0001F7E2 In {days_until} days"
            status_color = "green"

        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

            with col1:
                payee = sched['payee_name'] or "Unknown"
                st.markdown(f"**{payee}**")
                category = sched['category_name'] or "Uncategorized"
                st.caption(category)

            with col2:
                amount = milliunits_to_dollars(abs(sched['amount']))
                if sched['amount'] < 0:
                    st.markdown(f":red[-${amount:,.2f}]")
                else:
                    st.markdown(f":green[+${amount:,.2f}]")

            with col3:
                st.caption(item['next_date'].strftime("%b %d, %Y"))
                freq = sched['frequency'] or 'monthly'
                st.caption(freq.replace('_', ' ').title())

            with col4:
                st.caption(status)

            st.divider()
else:
    st.info("No transactions due in the next 30 days.")

st.divider()

# All recurring transactions table
st.subheader("All Recurring Transactions")

# Create dataframe
df = pd.DataFrame([
    {
        'Payee': sched['payee_name'] or 'Unknown',
        'Category': sched['category_name'] or 'Uncategorized',
        'Amount': milliunits_to_dollars(sched['amount']),
        'Frequency': (sched['frequency'] or 'monthly').replace('_', ' ').title(),
        'Next Date': sched['date_next'],
        'Account': sched['account_name'] or 'Unknown'
    }
    for sched in scheduled
])

# Sort options
sort_by = st.selectbox("Sort by", options=['Next Date', 'Amount', 'Payee', 'Category'])
ascending = st.checkbox("Ascending", value=True)

df_sorted = df.sort_values(by=sort_by, ascending=ascending)

st.dataframe(
    df_sorted.style.format({
        'Amount': '${:,.2f}'
    }),
    use_container_width=True
)

# Export option
st.divider()
csv = df_sorted.to_csv(index=False)
st.download_button(
    label="Download CSV",
    data=csv,
    file_name="recurring_transactions.csv",
    mime="text/csv"
)

# Frequency breakdown
st.divider()
st.subheader("Frequency Breakdown")

freq_counts = {}
for sched in scheduled:
    freq = (sched['frequency'] or 'monthly').replace('_', ' ').title()
    if freq not in freq_counts:
        freq_counts[freq] = {'count': 0, 'total': 0}
    freq_counts[freq]['count'] += 1
    freq_counts[freq]['total'] += abs(sched['amount'])

df_freq = pd.DataFrame([
    {
        'Frequency': freq,
        'Count': data['count'],
        'Total Amount': milliunits_to_dollars(data['total'])
    }
    for freq, data in freq_counts.items()
]).sort_values('Count', ascending=False)

col1, col2 = st.columns(2)

with col1:
    st.dataframe(
        df_freq.style.format({
            'Total Amount': '${:,.2f}'
        }),
        use_container_width=True
    )

with col2:
    import plotly.express as px
    fig = px.pie(df_freq, values='Count', names='Frequency', hole=0.4)
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
