"""Categories page - create, rename, regroup, and remove budget categories."""

import streamlit as st
from collections import OrderedDict

st.title("\U0001F3F7️ Categories")

db = st.session_state.get("db")
budget_id = st.session_state.get("budget_id")
if not db or not budget_id:
    st.warning("App not initialized.")
    st.stop()

categories = db.get_categories(budget_id, include_hidden=True)
groups = sorted({c["category_group_name"] or "Ungrouped" for c in categories})

# --- Add a category ---------------------------------------------------------
st.subheader("Add a category")
with st.form("add_cat", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        existing_or_new = st.selectbox("Group", groups + ["+ New group…"]) if groups else "+ New group…"
    with c2:
        new_group = st.text_input("New group name", placeholder="e.g. Bills")
        name = st.text_input("Category name", placeholder="e.g. Streaming")
    with c3:
        st.write("")
        submitted = st.form_submit_button("Add", type="primary")
    if submitted and name.strip():
        group = new_group.strip() if (existing_or_new == "+ New group…" or not groups) else existing_or_new
        if group:
            db.create_category(budget_id, group, name.strip())
            st.success(f"Added {group} › {name.strip()}")
            st.rerun()
        else:
            st.error("Pick or name a group.")

st.divider()

# --- Manage existing --------------------------------------------------------
st.subheader("Manage categories")
by_group = OrderedDict()
for c in sorted(categories, key=lambda x: (x["category_group_name"] or "", x["sort_order"] or 0, x["name"])):
    by_group.setdefault(c["category_group_name"] or "Ungrouped", []).append(c)

all_groups = list(by_group.keys())
for group, cats in by_group.items():
    st.markdown(f"#### {group}")
    for c in cats:
        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
        with col1:
            new_name = st.text_input("Name", value=c["name"], key=f"name_{c['id']}", label_visibility="collapsed")
        with col2:
            new_group = st.selectbox(
                "Group", all_groups, index=all_groups.index(group),
                key=f"grp_{c['id']}", label_visibility="collapsed",
            )
        with col3:
            if st.button("Save", key=f"save_{c['id']}"):
                if new_name.strip():
                    db.update_category(c["id"], new_name.strip(), new_group)
                    st.rerun()
        with col4:
            if st.button("Delete", key=f"del_{c['id']}", help="Transactions become uncategorized"):
                db.delete_category(c["id"])
                st.rerun()

st.caption(
    "Deleting a category leaves its transactions uncategorized and removes its "
    "assignments — it won't delete any transactions."
)
