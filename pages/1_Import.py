"""Import page - upload an OFX/QFX bank statement."""

import streamlit as st
import pandas as pd

from src.imports.service import ImportService
from src.imports.ofx import parse_ofx_bytes, OFXParseError
from src.utils.formatters import milliunits_to_dollars, format_currency, format_date

st.title("\U0001F4E5 Import a Statement")

db = st.session_state.get("db")
budget_id = st.session_state.get("budget_id")
if not db or not budget_id:
    st.warning("App not initialized.")
    st.stop()

st.markdown(
    "Upload an **OFX** or **QFX** file from your bank "
    "(in your bank's site, look for *Download* → *Quicken (.qfx)* or *Microsoft Money (.ofx)*). "
    "Everything stays on your machine."
)

uploaded = st.file_uploader("Bank statement", type=["ofx", "qfx"], accept_multiple_files=True)

if uploaded:
    for file in uploaded:
        data = file.getvalue()
        st.divider()
        st.subheader(file.name)

        # Preview before committing.
        try:
            accounts = parse_ofx_bytes(data)
        except OFXParseError as e:
            st.error(f"Couldn't parse this file: {e}")
            continue

        for acct in accounts:
            preview = pd.DataFrame([{
                "Date": format_date(t.posted) if t.posted else "—",
                "Payee": t.payee or "",
                "Memo": t.memo or "",
                "Amount": float(t.amount),
            } for t in acct.transactions])
            label = f"{acct.account_type or 'Account'} ••{(acct.account_id or '')[-4:]}"
            st.caption(
                f"**{label}** — {len(acct.transactions)} transactions"
                + (f", balance {format_currency(int((acct.balance or 0) * 1000))}" if acct.balance is not None else "")
            )
            if not preview.empty:
                st.dataframe(
                    preview.style.format({"Amount": "${:,.2f}"}),
                    use_container_width=True, hide_index=True, height=240,
                )

        if st.button(f"Import {file.name}", key=f"imp_{file.name}", type="primary"):
            svc = ImportService(db, budget_id)
            try:
                result = svc.import_file(file.name, data)
            except OFXParseError as e:
                st.error(f"Import failed: {e}")
                continue
            if result.already_imported_file and result.imported == 0:
                st.info("This file was already imported — no new transactions.")
            else:
                msg = f"Imported **{result.imported}** new transaction(s)"
                if result.duplicates:
                    msg += f" · skipped {result.duplicates} duplicate(s)"
                if result.auto_categorized:
                    msg += f" · auto-categorized {result.auto_categorized}"
                st.success(msg)
                if result.date_min:
                    st.caption(f"Covering {result.date_min} → {result.date_max}")
            uncategorized = db.count_uncategorized(budget_id)
            if uncategorized:
                st.info(f"\U0001F9FE {uncategorized} transaction(s) need a category — head to **Transactions**.")

# --- History ---------------------------------------------------------------
st.divider()
st.subheader("Import history")
batches = db.get_import_batches(budget_id)
if batches:
    hist = pd.DataFrame([{
        "When": str(b["imported_at"])[:16],
        "File": b["filename"],
        "Imported": b["txn_count"],
        "Duplicates": b["duplicate_count"],
        "Range": f"{b['date_min'] or '—'} → {b['date_max'] or '—'}",
    } for b in batches])
    st.dataframe(hist, use_container_width=True, hide_index=True)
else:
    st.caption("No imports yet.")
