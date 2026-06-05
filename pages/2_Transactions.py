"""Transactions page - categorize imported transactions and build rules."""

import streamlit as st
import pandas as pd

from src.imports.service import ImportService
from src.utils.formatters import milliunits_to_dollars

UNCATEGORIZED = "— Uncategorized —"

st.title("\U0001F9FE Transactions")

db = st.session_state.get("db")
budget_id = st.session_state.get("budget_id")
if not db or not budget_id:
    st.warning("App not initialized.")
    st.stop()

categories = db.get_categories(budget_id)
if not categories:
    st.info("Add some categories first on the **Categories** page.")
    st.stop()

# Build label <-> id maps (label includes group to stay unambiguous).
label_to_id = {f"{c['category_group_name']} › {c['name']}": c["id"] for c in categories}
id_to_label = {v: k for k, v in label_to_id.items()}
id_to_name = {c["id"]: c["name"] for c in categories}
options = [UNCATEGORIZED] + list(label_to_id.keys())

tab_uncat, tab_all, tab_rules = st.tabs(["Needs a category", "All transactions", "Rules"])

# --- Uncategorized: bulk-assign via an editable Category column -------------
with tab_uncat:
    uncategorized = db.get_uncategorized_transactions(budget_id)
    st.caption(f"{len(uncategorized)} transaction(s) need a category.")
    if uncategorized:
        df = pd.DataFrame([{
            "txn_id": t["id"],
            "Date": t["date"],
            "Payee": t["payee_name"] or "",
            "Memo": t["memo"] or "",
            "Amount": float(milliunits_to_dollars(t["amount"])),
            "Category": UNCATEGORIZED,
        } for t in uncategorized]).set_index("txn_id")

        edited = st.data_editor(
            df, use_container_width=True, hide_index=True, key="uncat_editor",
            disabled=["Date", "Payee", "Memo", "Amount"],
            column_config={
                "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "Category": st.column_config.SelectboxColumn("Category", options=options, required=True),
            },
        )
        assignments = [
            (txn_id, label_to_id[row["Category"]])
            for txn_id, row in edited.iterrows()
            if row["Category"] != UNCATEGORIZED
        ]
        if st.button(
            f"Categorize {len(assignments)} transaction(s)",
            type="primary", disabled=not assignments,
        ):
            for txn_id, cat_id in assignments:
                db.set_transaction_category(txn_id, cat_id, id_to_name[cat_id])
            st.rerun()
    else:
        st.success("Everything is categorized \U0001F389")

# --- All transactions (read-only, filterable) ------------------------------
with tab_all:
    txns = db.get_transactions(budget_id, limit=1000)
    if txns:
        df_all = pd.DataFrame([{
            "Date": t["date"],
            "Account": t["account_name"] or "",
            "Payee": t["payee_name"] or "",
            "Category": t["category_name"] or UNCATEGORIZED,
            "Amount": float(milliunits_to_dollars(t["amount"])),
        } for t in txns])
        cats_filter = st.multiselect("Filter by category", sorted(df_all["Category"].unique()))
        if cats_filter:
            df_all = df_all[df_all["Category"].isin(cats_filter)]
        st.dataframe(
            df_all.style.format({"Amount": "${:,.2f}"}),
            use_container_width=True, hide_index=True, height=420,
        )
    else:
        st.caption("No transactions yet — import a statement first.")

# --- Rules -----------------------------------------------------------------
with tab_rules:
    st.caption("Rules auto-categorize transactions on import (and can be applied now).")
    with st.form("new_rule", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            field = st.selectbox("When", ["payee", "memo"])
            mtype = st.selectbox("Match", ["contains", "equals", "regex"])
        with c2:
            pattern = st.text_input("Text / pattern", placeholder="e.g. WHOLE FOODS")
        with c3:
            target = st.selectbox("Assign to", list(label_to_id.keys()))
        apply_now = st.checkbox("Apply to existing uncategorized now", value=True)
        if st.form_submit_button("Add rule", type="primary") and pattern.strip():
            rid = db.add_rule(budget_id, pattern.strip(), label_to_id[target],
                              match_field=field, match_type=mtype)
            applied = ImportService(db, budget_id).apply_rule_to_existing(rid) if apply_now else 0
            st.success(f"Rule added." + (f" Categorized {applied} existing." if applied else ""))
            st.rerun()

    rules = db.get_rules(budget_id)
    if rules:
        for r in rules:
            rc1, rc2 = st.columns([6, 1])
            with rc1:
                st.markdown(
                    f"`{r['match_field']} {r['match_type']}` **{r['pattern']}** "
                    f"→ {r['group_name']} › {r['category_name']}"
                )
            with rc2:
                if st.button("Delete", key=f"del_rule_{r['id']}"):
                    db.delete_rule(r["id"])
                    st.rerun()
    else:
        st.caption("No rules yet.")
