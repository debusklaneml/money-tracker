"""Budget page - Give Every Dollar a Job.

The core loop: drive Ready to Assign to zero by assigning every dollar to a
category. Assignments are written straight to the local database.
"""

import streamlit as st
import pandas as pd

from src.budget.engine import BudgetEngine, current_month
from src.utils.formatters import (
    milliunits_to_dollars,
    dollars_to_milliunits,
    format_currency,
    format_month,
)

st.title("\U0001F4B5 Give Every Dollar a Job")

db = st.session_state.get("db")
budget_id = st.session_state.get("budget_id")
if not db or not budget_id:
    st.warning("App not initialized.")
    st.stop()

engine = BudgetEngine(db, budget_id)
month = current_month()
state = engine.get_state(month)

st.caption(f"Budgeting **{format_month(month)}**")

# --- Ready to Assign --------------------------------------------------------
rta = state.ready_to_assign
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    if rta > 0:
        st.success(f"### \U0001F4B0 {format_currency(rta)} Ready to Assign")
        st.caption("Give these dollars a job in the envelopes below.")
    elif rta < 0:
        st.error(f"### ⚠️ {format_currency(rta)} Over-Assigned")
        st.caption("You've assigned more than you have — pull some back.")
    else:
        st.info("### ✅ $0.00 — Every dollar has a job")
with c2:
    st.metric("Income (this month)", format_currency(state.income_month))
with c3:
    st.metric("Assigned (all time)", format_currency(state.assigned_total))

if not state.categories:
    st.info("No categories yet. Add some on the **Categories** page.")
    st.stop()

st.divider()

# --- Envelope editor --------------------------------------------------------
st.subheader("Envelopes")
st.caption("Edit **Assigned**, then click *Apply assignments*.")

rows = [{
    "category_id": c.id,
    "Group": c.group,
    "Category": c.name,
    "Assigned": float(milliunits_to_dollars(c.assigned)),
    "Activity": float(milliunits_to_dollars(c.activity)),
    "Available": float(milliunits_to_dollars(c.available)),
} for c in state.categories]
df = pd.DataFrame(rows).set_index("category_id")

edited = st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    disabled=["Group", "Category", "Activity", "Available"],
    column_config={
        "Assigned": st.column_config.NumberColumn("Assigned", format="$%.2f", min_value=0.0, step=1.0),
        "Activity": st.column_config.NumberColumn("Activity", format="$%.2f"),
        "Available": st.column_config.NumberColumn(
            "Available", format="$%.2f", help="Rolls over month to month; negative = overspent"
        ),
    },
    key="envelope_editor",
)

changes = []
for cat_id, row in edited.iterrows():
    new_milli = dollars_to_milliunits(round(float(row["Assigned"]), 2))
    old_milli = dollars_to_milliunits(round(float(df.loc[cat_id, "Assigned"]), 2))
    if new_milli != old_milli:
        changes.append((cat_id, new_milli))

apply_col, info_col = st.columns([1, 2])
with apply_col:
    if st.button(
        f"Apply assignments ({len(changes)})" if changes else "Apply assignments",
        type="primary", disabled=not changes, use_container_width=True,
    ):
        for cat_id, new_milli in changes:
            engine.assign(cat_id, new_milli, month=month)
        st.rerun()
with info_col:
    if changes:
        net = sum(
            new - dollars_to_milliunits(round(float(df.loc[cid, "Assigned"]), 2))
            for cid, new in changes
        )
        st.caption(
            f"{len(changes)} pending · Ready to Assign will become "
            f"**{format_currency(rta - net)}**."
        )

st.divider()

# --- Move money / cover overspending ---------------------------------------
st.subheader("Move money between envelopes")
overspent = state.overspent
if overspent:
    total_over = sum(c.available for c in overspent)
    st.warning(
        f"\U0001F534 {len(overspent)} overspent envelope(s) "
        f"({format_currency(total_over)}). Cover them below."
    )

by_id = {c.id: c for c in state.categories}
ids = list(by_id.keys())
label = lambda i: f"{by_id[i].group} › {by_id[i].name}"

m1, m2, m3, m4 = st.columns([3, 3, 2, 2])
with m1:
    from_id = st.selectbox("From", ids, format_func=label)
    st.caption(f"Available: {format_currency(by_id[from_id].available)}")
with m2:
    default_to = ids.index(min(overspent, key=lambda c: c.available).id) if overspent else 0
    to_id = st.selectbox("To", ids, index=default_to, format_func=label)
    st.caption(f"Available: {format_currency(by_id[to_id].available)}")
with m3:
    amount = st.number_input("Amount ($)", min_value=0.0, step=1.0, value=0.0)
with m4:
    st.write("")
    st.write("")
    if st.button("Move", use_container_width=True, disabled=amount <= 0 or from_id == to_id):
        engine.move(from_id, to_id, dollars_to_milliunits(round(amount, 2)), month=month)
        st.rerun()
