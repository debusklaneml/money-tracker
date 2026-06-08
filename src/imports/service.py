"""Import service: turn an uploaded OFX/QFX file into categorized transactions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from src.cache.database import Database, LOCAL_BUDGET_ID
from src.imports.classifier import (
    Category,
    TransactionClassifier,
    TxnToClassify,
    build_default_classifier,
)
from src.imports.ofx import parse_ofx_bytes, OFXAccount
from src.utils.formatters import dollars_to_milliunits

_TYPE_LABEL = {
    "CHECKING": "Checking",
    "SAVINGS": "Savings",
    "CREDITCARD": "Credit Card",
    "MONEYMRKT": "Money Market",
    "CREDITLINE": "Line of Credit",
}


@dataclass
class ImportResult:
    filename: str
    accounts: list[str] = field(default_factory=list)
    imported: int = 0
    duplicates: int = 0
    auto_categorized: int = 0
    ai_categorized: int = 0
    already_imported_file: bool = False
    date_min: Optional[str] = None
    date_max: Optional[str] = None


def _account_label(acct: OFXAccount) -> str:
    label = _TYPE_LABEL.get(acct.account_type or "", (acct.account_type or "Account").title())
    last4 = (acct.account_id or "")[-4:]
    return f"{label} ••{last4}" if last4 else label


def _compile_rule(rule) -> tuple:
    """Return (field, predicate) for a stored rule row."""
    pattern, mtype = rule["pattern"], rule["match_type"]
    field_name = rule["match_field"]
    if mtype == "equals":
        pred = lambda v: v.strip().lower() == pattern.strip().lower()
    elif mtype == "regex":
        rx = re.compile(pattern, re.IGNORECASE)
        pred = lambda v: bool(rx.search(v))
    else:  # contains
        needle = pattern.strip().lower()
        pred = lambda v: needle in v.lower()
    return field_name, pred


class ImportService:
    def __init__(
        self,
        db: Database,
        budget_id: str = LOCAL_BUDGET_ID,
        classifier: Optional[TransactionClassifier] = None,
    ):
        self.db = db
        self.budget_id = budget_id
        # AI fallback for entries no rule matched. Defaults to the
        # environment-gated classifier (a no-op offline / without a key);
        # tests inject a stub. Construction never touches the network.
        self.classifier = classifier if classifier is not None else build_default_classifier()

    def _match_category(self, rules_compiled, payee: str, memo: str) -> Optional[tuple]:
        for field_name, pred, cat_id, cat_name in rules_compiled:
            value = payee if field_name == "payee" else memo
            if value and pred(value):
                return cat_id, cat_name
        return None

    def import_file(self, filename: str, data: bytes) -> ImportResult:
        """Parse and import an OFX/QFX file. Idempotent via FITID + file-hash."""
        result = ImportResult(filename=filename)
        file_hash = hashlib.sha256(data).hexdigest()
        if self.db.file_hash_imported(self.budget_id, file_hash):
            result.already_imported_file = True
            # Still parse: re-importing only adds genuinely new FITIDs (dedup below).

        accounts = parse_ofx_bytes(data)

        # Pre-compile categorization rules once.
        rules_compiled = []
        for r in self.db.get_rules(self.budget_id):
            fname, pred = _compile_rule(r)
            rules_compiled.append((fname, pred, r["category_id"], r["category_name"]))

        all_dates: list[str] = []
        # Transactions no rule matched, collected across all accounts so the AI
        # fallback runs as a single batched call after inserts. Each tuple is
        # (inserted_txn_id, TxnToClassify).
        unmatched: list[tuple[str, TxnToClassify]] = []
        for acct in accounts:
            if not acct.account_id:
                continue
            name = _account_label(acct)
            account_id = self.db.upsert_imported_account(
                self.budget_id,
                account_number=acct.account_id,
                name=name,
                account_type=(acct.account_type or "OTHER").lower(),
                on_budget=True,
                balance=dollars_to_milliunits(acct.balance) if acct.balance is not None else 0,
            )
            result.accounts.append(name)

            batch_id = self.db.create_import_batch(self.budget_id, account_id, filename, file_hash)
            imported = dups = auto = 0
            batch_dates: list[str] = []

            for txn in acct.transactions:
                if not txn.fitid or not txn.posted:
                    continue
                if self.db.transaction_exists(account_id, txn.fitid):
                    dups += 1
                    continue

                payee = txn.payee or ""
                memo = txn.memo or ""
                match = self._match_category(rules_compiled, payee, memo)
                cat_id, cat_name = match if match else (None, None)
                if match:
                    auto += 1

                amount = dollars_to_milliunits(txn.amount)
                date_str = txn.posted.isoformat()
                batch_dates.append(date_str)
                txn_id = self.db.insert_imported_transaction(
                    budget_id=self.budget_id,
                    account_id=account_id,
                    account_name=name,
                    fitid=txn.fitid,
                    txn_date=date_str,
                    amount=amount,
                    payee_name=txn.payee,
                    memo=txn.memo,
                    category_id=cat_id,
                    category_name=cat_name,
                    import_batch_id=batch_id,
                )
                imported += 1
                if not match:
                    unmatched.append(
                        (txn_id, TxnToClassify(payee=payee, memo=memo, amount=amount))
                    )

            self.db.finalize_import_batch(
                batch_id, imported, dups,
                min(batch_dates) if batch_dates else None,
                max(batch_dates) if batch_dates else None,
            )
            result.imported += imported
            result.duplicates += dups
            result.auto_categorized += auto
            all_dates.extend(batch_dates)

        # AI fallback: label entries no rule matched, picking from existing
        # categories. No-ops (leaving them uncategorized) when the classifier is
        # disabled / offline. Applied as a post-pass so it's a single LLM call.
        result.ai_categorized = self._ai_categorize(unmatched)

        if all_dates:
            result.date_min, result.date_max = min(all_dates), max(all_dates)
        return result

    def _ai_categorize(self, unmatched: list[tuple[str, TxnToClassify]]) -> int:
        """Label rule-unmatched transactions via the AI classifier.

        Returns the count actually assigned a category. Safe to call when the
        classifier is disabled (returns 0) — it short-circuits before touching
        the DB or building any request.
        """
        if not unmatched or not self.classifier.enabled:
            return 0

        category_rows = self.db.get_categories(self.budget_id)
        categories = [
            Category(
                id=row["id"],
                name=row["name"],
                group=row["category_group_name"],
            )
            for row in category_rows
        ]
        if not categories:
            return 0
        name_by_id = {c.id: c.name for c in categories}

        txns = [t for _, t in unmatched]
        chosen = self.classifier.classify_batch(txns, categories)

        assigned = 0
        for (txn_id, _), cat_id in zip(unmatched, chosen):
            if cat_id and cat_id in name_by_id:
                self.db.set_transaction_category(txn_id, cat_id, name_by_id[cat_id])
                assigned += 1
        return assigned

    def apply_rule_to_existing(self, rule_id: int) -> int:
        """Apply one rule to existing uncategorized transactions; returns count."""
        rule = next((r for r in self.db.get_rules(self.budget_id) if r["id"] == rule_id), None)
        if not rule:
            return 0
        field_name, pred = _compile_rule(rule)
        count = 0
        for txn in self.db.get_uncategorized_transactions(self.budget_id):
            value = (txn["payee_name"] if field_name == "payee" else txn["memo"]) or ""
            if value and pred(value):
                self.db.set_transaction_category(txn["id"], rule["category_id"], rule["category_name"])
                count += 1
        return count
