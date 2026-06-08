"""Import-flow tests for the AI auto-classify fallback (bead bud-pco).

Uses a real :class:`Database` on a temp SQLite file plus an injected stub
classifier — NO network calls. Verifies:

* rule-unmatched entries get the AI-chosen category, and ``ai_categorized``
  counts them (distinct from rule-based ``auto_categorized``);
* entries matched by a rule are NOT overridden by the AI;
* with the classifier disabled, import still works and leaves unmatched
  entries uncategorized.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.cache.database import Database
from src.imports.classifier import TransactionClassifier
from src.imports.service import ImportService

# Two txns: a grocery store (no rule) and an employer paycheck (a rule will
# match this one in the override test).
SAMPLE_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<ACCTID>123456789
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260101120000
<TRNAMT>-25.00
<FITID>TXN-0001
<NAME>Whole Foods Market
<MEMO>Groceries
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260103120000
<TRNAMT>1500.00
<FITID>TXN-0002
<NAME>Acme Employer
<MEMO>Paycheck
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>1475.00
<DTASOF>20260103120000
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


@pytest.fixture()
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    database = Database(db_path)
    database.ensure_local_budget()
    try:
        yield database
    finally:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()


def _category_id_by_name(db, budget_id, name):
    for row in db.get_categories(budget_id):
        if row["name"] == name:
            return row["id"]
    raise AssertionError(f"category {name!r} not found")


def _txn_categories(db, budget_id):
    """Map FITID -> category_id for the imported transactions."""
    with db._get_connection() as conn:
        rows = conn.execute(
            "SELECT import_id, category_id FROM transactions WHERE budget_id = ?",
            (budget_id,),
        ).fetchall()
    return {r["import_id"]: r["category_id"] for r in rows}


def _stub_classifier(answer_by_index):
    """Classifier whose LLM call returns category ids keyed by batch index."""

    def _call(model, system, tool, messages):
        return {
            "assignments": [
                {"index": i, "category_id": cid, "confidence": 0.95}
                for i, cid in answer_by_index.items()
            ]
        }

    return TransactionClassifier(_call)


def test_ai_categorizes_unmatched(db):
    budget_id = db.ensure_local_budget()
    groceries = db.create_category(budget_id, "Everyday", "Groceries")
    income = db.create_category(budget_id, "Income", "Paycheck")

    # No rules. Both txns are unmatched -> both go to the classifier (batch
    # order follows insertion: index 0 = groceries txn, index 1 = paycheck).
    clf = _stub_classifier({0: groceries, 1: income})
    svc = ImportService(db, budget_id, classifier=clf)
    result = svc.import_file("statement.ofx", SAMPLE_OFX)

    assert result.imported == 2
    assert result.auto_categorized == 0  # no rules matched
    assert result.ai_categorized == 2

    cats = _txn_categories(db, budget_id)
    assert cats["TXN-0001"] == groceries
    assert cats["TXN-0002"] == income


def test_rule_match_not_overridden_by_ai(db):
    budget_id = db.ensure_local_budget()
    db.create_category(budget_id, "Everyday", "Groceries")
    income = db.create_category(budget_id, "Income", "Paycheck")
    misc = db.create_category(budget_id, "Everyday", "Misc")

    # Rule matches the paycheck txn -> rule wins, never sent to the AI.
    db.add_rule(budget_id, "Acme Employer", income, match_field="payee", match_type="contains")

    # The stub would assign EVERYTHING to "misc" if asked. Only the unmatched
    # grocery txn should be in the batch (index 0), so the paycheck keeps the
    # rule category and is not clobbered.
    clf = _stub_classifier({0: misc, 1: misc})
    svc = ImportService(db, budget_id, classifier=clf)
    result = svc.import_file("statement.ofx", SAMPLE_OFX)

    assert result.imported == 2
    assert result.auto_categorized == 1  # paycheck matched the rule
    assert result.ai_categorized == 1  # only the grocery txn

    cats = _txn_categories(db, budget_id)
    assert cats["TXN-0002"] == income  # rule, NOT overridden by AI's "misc"
    assert cats["TXN-0001"] == misc  # AI labeled the unmatched grocery txn


def test_disabled_classifier_leaves_uncategorized(db):
    budget_id = db.ensure_local_budget()
    db.create_category(budget_id, "Everyday", "Groceries")

    svc = ImportService(db, budget_id, classifier=TransactionClassifier(None))
    result = svc.import_file("statement.ofx", SAMPLE_OFX)

    assert result.imported == 2
    assert result.auto_categorized == 0
    assert result.ai_categorized == 0

    cats = _txn_categories(db, budget_id)
    assert cats["TXN-0001"] is None
    assert cats["TXN-0002"] is None


def test_default_service_offline_no_network(db, monkeypatch):
    """Without a key, the default-constructed service imports fully, no network."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BUD_AI_CATEGORIZE", raising=False)
    budget_id = db.ensure_local_budget()

    svc = ImportService(db, budget_id)  # builds the default (disabled) classifier
    assert svc.classifier.enabled is False
    result = svc.import_file("statement.ofx", SAMPLE_OFX)

    assert result.imported == 2
    assert result.ai_categorized == 0
