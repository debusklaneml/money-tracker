"""Alerts page - View and manage financial alerts."""

import streamlit as st
import json
from datetime import datetime

from src.alerts import AlertRegistry, AlertType, save_alerts_to_db
from src.utils.formatters import milliunits_to_dollars

st.title("\U0001F514 Alerts")

# Get resources from session state
db = st.session_state.get('db')
budget_id = st.session_state.get('budget_id')

if not db or not budget_id:
    st.warning("Please select a budget from the sidebar")
    st.stop()

# Alert controls
col1, col2, col3 = st.columns(3)

with col1:
    severity_filter = st.multiselect(
        "Severity",
        options=["critical", "warning", "info"],
        default=["critical", "warning"]
    )

with col2:
    type_filter = st.multiselect(
        "Alert Type",
        options=[t.value for t in AlertType],
        default=[t.value for t in AlertType],
        format_func=lambda x: x.replace("_", " ").title()
    )

with col3:
    show_dismissed = st.checkbox("Show Dismissed", value=False)

# Run detection button
st.divider()

col1, col2 = st.columns([2, 1])
with col1:
    if st.button("\U0001F50D Run Alert Detection", type="primary"):
        with st.spinner("Analyzing transactions and detecting alerts..."):
            try:
                # Run all detectors
                new_alerts = AlertRegistry.run_all(budget_id, db)

                # Save to database
                saved_count = save_alerts_to_db(db, budget_id, new_alerts)

                if saved_count > 0:
                    st.success(f"Detected {saved_count} new alert(s)!")
                else:
                    st.info("No new alerts detected.")

                st.rerun()
            except Exception as e:
                st.error(f"Error running detection: {e}")

with col2:
    st.caption("Run detection to check for unusual spending, budget issues, and recurring transaction changes.")

st.divider()

# Fetch alerts
alerts = db.get_alerts(
    budget_id=budget_id,
    include_dismissed=show_dismissed,
    severities=severity_filter if severity_filter else None,
    alert_types=type_filter if type_filter else None,
    limit=100
)

# Summary stats
if alerts:
    critical_count = sum(1 for a in alerts if a['severity'] == 'critical')
    warning_count = sum(1 for a in alerts if a['severity'] == 'warning')
    info_count = sum(1 for a in alerts if a['severity'] == 'info')

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Alerts", len(alerts))
    with col2:
        st.metric("Critical", critical_count, delta=None if critical_count == 0 else "needs attention", delta_color="inverse")
    with col3:
        st.metric("Warnings", warning_count)
    with col4:
        st.metric("Info", info_count)

    st.divider()

# Display alerts
if not alerts:
    st.success("\u2705 No alerts matching your filters!")
    st.balloons()
else:
    st.caption(f"Showing {len(alerts)} alert(s)")

    for alert in alerts:
        severity = alert['severity']
        alert_type = alert['alert_type']

        # Severity styling
        severity_config = {
            "critical": {"icon": "\U0001F534", "color": "red"},
            "warning": {"icon": "\U0001F7E0", "color": "orange"},
            "info": {"icon": "\U0001F535", "color": "blue"}
        }
        config = severity_config.get(severity, {"icon": "\u26AA", "color": "gray"})

        # Expandable alert card
        is_critical = severity == "critical"
        with st.expander(f"{config['icon']} {alert['title']}", expanded=is_critical):

            # Alert details
            st.markdown(alert['description'])

            # Metadata
            if alert['metadata']:
                try:
                    metadata = json.loads(alert['metadata']) if isinstance(alert['metadata'], str) else alert['metadata']

                    st.caption("Details:")

                    # Format specific metadata nicely
                    if 'amount' in metadata:
                        st.write(f"**Amount:** ${milliunits_to_dollars(metadata['amount']):,.2f}")
                    if 'mz_score' in metadata:
                        st.write(f"**Anomaly Score:** {metadata['mz_score']:.2f}")
                    if 'payee' in metadata:
                        st.write(f"**Payee:** {metadata['payee']}")
                    if 'category' in metadata:
                        st.write(f"**Category:** {metadata['category']}")
                    if 'ratio' in metadata:
                        st.write(f"**Budget Usage:** {metadata['ratio']:.0%}")
                    if 'days_overdue' in metadata:
                        st.write(f"**Days Overdue:** {metadata['days_overdue']}")
                    if 'expected_date' in metadata:
                        st.write(f"**Expected Date:** {metadata['expected_date']}")

                except (json.JSONDecodeError, TypeError):
                    pass

            # Timestamps
            col1, col2 = st.columns(2)
            with col1:
                created = alert['created_at']
                if created:
                    st.caption(f"Created: {created}")
            with col2:
                if alert['acknowledged_at']:
                    st.caption(f"Acknowledged: {alert['acknowledged_at']}")

            # Alert type badge
            type_label = alert_type.replace("_", " ").title()
            st.caption(f"Type: {type_label}")

            # Action buttons
            st.divider()
            btn_col1, btn_col2, btn_col3 = st.columns(3)

            with btn_col1:
                if not alert['acknowledged_at']:
                    if st.button("Acknowledge", key=f"ack_{alert['id']}"):
                        db.acknowledge_alert(alert['id'])
                        st.success("Alert acknowledged")
                        st.rerun()
                else:
                    st.caption("\u2714 Acknowledged")

            with btn_col2:
                if not alert['dismissed']:
                    if st.button("Dismiss", key=f"dismiss_{alert['id']}"):
                        db.dismiss_alert(alert['id'])
                        st.info("Alert dismissed")
                        st.rerun()

            with btn_col3:
                # Link to related entity if applicable
                if alert['related_entity_type'] == 'transaction' and alert['related_entity_id']:
                    st.caption(f"Transaction: {alert['related_entity_id'][:8]}...")
                elif alert['related_entity_type'] == 'category' and alert['related_entity_id']:
                    st.caption(f"Category: {alert['related_entity_id'][:8]}...")

# Alert type explanations
st.divider()
with st.expander("\u2139\ufe0f About Alert Types"):
    st.markdown("""
    ### Unusual Spending
    Detects transactions significantly higher or lower than your typical spending in a category.
    Uses **Modified Z-Score** statistical analysis for robust outlier detection.

    - **Warning**: Spending 2.5+ standard deviations from typical
    - **Critical**: Spending 3.5+ standard deviations from typical

    ### Budget Overspending
    Monitors your budget categories for overspending.

    - **Info**: 90%+ of budget used
    - **Critical**: Over budget

    ### Recurring Changes
    Tracks your scheduled/recurring transactions.

    - **Amount Changed**: When a recurring charge differs from expected
    - **Missing**: When an expected recurring transaction hasn't appeared

    ---

    **Thresholds can be customized in Settings.**
    """)
