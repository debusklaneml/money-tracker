"""Unit tests for the AI transaction classifier (bead bud-pco).

The LLM call is always a stub — these tests make NO network calls. They verify
that the classifier maps AI answers onto existing category ids, discards
hallucinated/unknown ids and low-confidence guesses, and degrades gracefully to
all-``None`` when disabled, when there are no categories, or when the call errors
or returns junk.
"""

from __future__ import annotations

from src.imports.classifier import (
    Category,
    TransactionClassifier,
    TxnToClassify,
    build_default_classifier,
)

CATS = [
    Category(id="cat-groceries", name="Groceries", group="Everyday"),
    Category(id="cat-coffee", name="Coffee Shops", group="Everyday"),
    Category(id="cat-income", name="Paycheck", group="Income"),
]

TXNS = [
    TxnToClassify(payee="Whole Foods", memo="", amount=-50000),
    TxnToClassify(payee="Blue Bottle", memo="Latte", amount=-6000),
]


def _stub(assignments):
    """Build an LLMCall stub returning the given assignments dict."""

    def _call(model, system, tool, messages):
        return {"assignments": assignments}

    return _call


def test_maps_answers_to_existing_ids():
    clf = TransactionClassifier(
        _stub(
            [
                {"index": 0, "category_id": "cat-groceries", "confidence": 0.95},
                {"index": 1, "category_id": "cat-coffee", "confidence": 0.9},
            ]
        )
    )
    assert clf.classify_batch(TXNS, CATS) == ["cat-groceries", "cat-coffee"]


def test_hallucinated_ids_are_discarded():
    clf = TransactionClassifier(
        _stub(
            [
                {"index": 0, "category_id": "cat-does-not-exist", "confidence": 0.99},
                {"index": 1, "category_id": "cat-coffee", "confidence": 0.99},
            ]
        )
    )
    # Unknown id -> None; valid id kept.
    assert clf.classify_batch(TXNS, CATS) == [None, "cat-coffee"]


def test_low_confidence_left_uncategorized():
    clf = TransactionClassifier(
        _stub(
            [
                {"index": 0, "category_id": "cat-groceries", "confidence": 0.2},
                {"index": 1, "category_id": "cat-coffee", "confidence": 0.85},
            ]
        ),
        min_confidence=0.6,
    )
    assert clf.classify_batch(TXNS, CATS) == [None, "cat-coffee"]


def test_explicit_null_category_is_none():
    clf = TransactionClassifier(
        _stub(
            [
                {"index": 0, "category_id": None, "confidence": 0.9},
                {"index": 1, "category_id": "cat-coffee", "confidence": 0.9},
            ]
        )
    )
    assert clf.classify_batch(TXNS, CATS) == [None, "cat-coffee"]


def test_missing_assignment_index_left_none():
    # Model only answered for index 1; index 0 stays uncategorized.
    clf = TransactionClassifier(
        _stub([{"index": 1, "category_id": "cat-coffee", "confidence": 0.9}])
    )
    assert clf.classify_batch(TXNS, CATS) == [None, "cat-coffee"]


def test_out_of_range_index_ignored():
    clf = TransactionClassifier(
        _stub([{"index": 99, "category_id": "cat-coffee", "confidence": 0.9}])
    )
    assert clf.classify_batch(TXNS, CATS) == [None, None]


def test_disabled_classifier_is_noop():
    clf = TransactionClassifier(None)
    assert clf.enabled is False
    assert clf.classify_batch(TXNS, CATS) == [None, None]


def test_no_categories_returns_all_none():
    clf = TransactionClassifier(_stub([{"index": 0, "category_id": "x", "confidence": 1.0}]))
    assert clf.classify_batch(TXNS, []) == [None, None]


def test_empty_input_returns_empty():
    clf = TransactionClassifier(_stub([]))
    assert clf.classify_batch([], CATS) == []


def test_call_raising_degrades_to_none():
    def _boom(model, system, tool, messages):
        raise RuntimeError("network down")

    clf = TransactionClassifier(_boom)
    assert clf.classify_batch(TXNS, CATS) == [None, None]


def test_malformed_response_degrades_to_none():
    def _junk(model, system, tool, messages):
        return {"unexpected": "shape"}  # no "assignments" key

    clf = TransactionClassifier(_junk)
    assert clf.classify_batch(TXNS, CATS) == [None, None]


def test_none_response_degrades_to_none():
    def _none(model, system, tool, messages):
        return None

    clf = TransactionClassifier(_none)
    assert clf.classify_batch(TXNS, CATS) == [None, None]


def test_garbage_confidence_treated_as_low():
    clf = TransactionClassifier(
        _stub([{"index": 0, "category_id": "cat-groceries", "confidence": "high"}])
    )
    # Non-numeric confidence -> 0.0 -> below threshold -> None.
    assert clf.classify_batch(TXNS, CATS) == [None, None]


# --- build_default_classifier env gating (no network either way) -------------


def test_default_disabled_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BUD_AI_CATEGORIZE", raising=False)
    clf = build_default_classifier()
    assert clf.enabled is False


def test_default_force_disabled_even_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("BUD_AI_CATEGORIZE", "0")
    clf = build_default_classifier()
    assert clf.enabled is False
