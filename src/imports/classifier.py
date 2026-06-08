"""AI-assisted transaction classifier (bead bud-pco).

A graceful-degradation fallback for the rules-based categorizer in
:mod:`src.imports.service`. When a freshly imported transaction matches no
user-defined rule, the importer can ask this classifier to pick a category from
the budget's EXISTING category list. The model never invents categories — any
answer that doesn't map back to a real category id is discarded, and
low-confidence answers leave the transaction uncategorized.

Design goals
------------
* **Offline-safe.** If there is no ``ANTHROPIC_API_KEY`` (or AI is disabled, or
  the ``anthropic`` SDK isn't installed, or any error occurs), the classifier
  no-ops and returns ``None`` for every transaction. Import must always succeed
  fully offline — nothing here is allowed to raise into the import flow.
* **Injectable / mockable.** The actual LLM call is a ``Callable`` stored on the
  instance. Tests pass a stub; production lazily builds an Anthropic-backed one.
  No network is touched at construction time.
* **Cheap and batched.** All unmatched transactions from a file go in a single
  tool-use call, so one import is one (small, fast-model) request.

The public surface is small:

* :class:`Category` / :class:`TxnToClassify` — typed inputs.
* :class:`TransactionClassifier` — holds the (possibly absent) LLM callable and
  exposes :meth:`classify_batch`.
* :func:`build_default_classifier` — environment-gated factory used by the
  import service.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

logger = logging.getLogger(__name__)

# Cheap, fast model for high-volume classification. Confirmed current id from
# the claude-api skill's model table (Haiku tier).
DEFAULT_MODEL = "claude-haiku-4-5"

# Below this the model's pick is treated as "not sure" -> leave uncategorized.
DEFAULT_MIN_CONFIDENCE = 0.6

# Env var that opts AI classification in/out. Defaults to ON only when a key is
# present (see :func:`build_default_classifier`).
ENABLE_ENV = "BUD_AI_CATEGORIZE"
API_KEY_ENV = "ANTHROPIC_API_KEY"
MODEL_ENV = "BUD_AI_CATEGORIZE_MODEL"


@dataclass(frozen=True)
class Category:
    """An existing category the model is allowed to choose from."""

    id: str
    name: str
    group: Optional[str] = None


@dataclass(frozen=True)
class TxnToClassify:
    """A single transaction to label.

    ``amount`` is signed milliunits (the app-wide convention); it is shown to
    the model purely as context and is never modified.
    """

    payee: str
    memo: str
    amount: int


@dataclass(frozen=True)
class Classification:
    """The classifier's answer for one transaction."""

    category_id: Optional[str]
    confidence: float


# A LLMCall takes (model, system, tool, messages) and returns the parsed tool
# input dict the model produced, or ``None`` if nothing usable came back. Kept
# deliberately thin so tests can substitute a plain function.
LLMCall = Callable[[str, str, dict, list], Optional[dict]]


_TOOL_NAME = "record_categories"

_SYSTEM_PROMPT = (
    "You are a personal-finance bookkeeping assistant. You are given a list of "
    "bank transactions (payee, memo, and signed amount in dollars) and a fixed "
    "list of budget categories. For each transaction, choose the single best "
    "matching category from the provided list, or leave it unassigned if none "
    "is a clearly appropriate fit. Only ever use category ids from the provided "
    "list — never invent a category. Provide a confidence between 0 and 1 "
    "reflecting how sure you are; use a low confidence (or omit the category) "
    "when the transaction is ambiguous."
)


def _build_tool(categories: Sequence[Category]) -> dict:
    """JSON-schema tool the model fills in — one entry per input transaction."""
    valid_ids = [c.id for c in categories]
    return {
        "name": _TOOL_NAME,
        "description": (
            "Record the chosen category for each transaction, in the same order "
            "they were given. Use null for category_id when no category fits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assignments": {
                    "type": "array",
                    "description": "One entry per transaction, in input order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "0-based index of the transaction.",
                            },
                            "category_id": {
                                "type": ["string", "null"],
                                "enum": valid_ids + [None],
                                "description": "An id from the category list, or null.",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "0..1 confidence in this choice.",
                            },
                        },
                        "required": ["index", "category_id", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["assignments"],
            "additionalProperties": False,
        },
    }


def _milliunits_to_dollars(amount: int) -> str:
    return f"{amount / 1000:.2f}"


def _build_user_message(
    txns: Sequence[TxnToClassify], categories: Sequence[Category]
) -> list:
    cat_lines = [
        f"- id={c.id} | {c.name}" + (f" ({c.group})" if c.group else "")
        for c in categories
    ]
    txn_lines = [
        f"[{i}] payee={t.payee!r} memo={t.memo!r} amount=${_milliunits_to_dollars(t.amount)}"
        for i, t in enumerate(txns)
    ]
    text = (
        "Categories:\n"
        + "\n".join(cat_lines)
        + "\n\nTransactions:\n"
        + "\n".join(txn_lines)
        + f"\n\nCall {_TOOL_NAME} with one assignment per transaction (indices 0.."
        + f"{len(txns) - 1})."
    )
    return [{"role": "user", "content": text}]


class TransactionClassifier:
    """Maps AI answers onto real category ids, with graceful degradation.

    Construct with an explicit ``llm_call`` (e.g. a test stub), or pass ``None``
    to disable AI entirely (every transaction comes back uncategorized). The
    instance is cheap and holds no network resources.
    """

    def __init__(
        self,
        llm_call: Optional[LLMCall],
        *,
        model: str = DEFAULT_MODEL,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self._llm_call = llm_call
        self._model = model
        self._min_confidence = min_confidence

    @property
    def enabled(self) -> bool:
        """True when an LLM callable is wired up; False means pure no-op."""
        return self._llm_call is not None

    def classify_batch(
        self,
        txns: Sequence[TxnToClassify],
        categories: Sequence[Category],
    ) -> list[Optional[str]]:
        """Classify a batch; returns a category id (or ``None``) per input txn.

        Never raises: on any failure (disabled, no categories, SDK/network
        error, malformed response) it returns all-``None`` of the right length.
        Returned ids are guaranteed to exist in ``categories``; low-confidence
        and hallucinated answers are dropped to ``None``.
        """
        n = len(txns)
        if n == 0:
            return []
        if not self.enabled or not categories:
            return [None] * n

        valid_ids = {c.id for c in categories}
        tool = _build_tool(categories)
        messages = _build_user_message(txns, categories)

        try:
            parsed = self._llm_call(self._model, _SYSTEM_PROMPT, tool, messages)
        except Exception:  # noqa: BLE001 — degrade gracefully, never break import
            logger.warning("AI classification call failed; leaving uncategorized.", exc_info=True)
            return [None] * n

        if not parsed:
            return [None] * n

        results: list[Optional[str]] = [None] * n
        for entry in parsed.get("assignments", []):
            try:
                idx = int(entry["index"])
            except (KeyError, TypeError, ValueError):
                continue
            if not 0 <= idx < n:
                continue
            cat_id = entry.get("category_id")
            try:
                confidence = float(entry.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            # Discard hallucinated ids and low-confidence guesses.
            if cat_id in valid_ids and confidence >= self._min_confidence:
                results[idx] = cat_id
        return results


def _anthropic_llm_call(api_key: Optional[str] = None) -> Optional[LLMCall]:
    """Build an Anthropic-backed :data:`LLMCall`, or ``None`` if unavailable.

    The ``anthropic`` SDK is imported lazily here so the rest of the app never
    hard-depends on it.
    """
    try:
        import anthropic  # noqa: PLC0415 — lazy by design
    except ImportError:
        logger.info("anthropic SDK not installed; AI categorization disabled.")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    except Exception:  # noqa: BLE001
        logger.info("Could not construct Anthropic client; AI categorization disabled.", exc_info=True)
        return None

    def _call(model: str, system: str, tool: dict, messages: list) -> Optional[dict]:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=messages,
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                # block.input is already a parsed dict; be defensive anyway.
                if isinstance(block.input, dict):
                    return block.input
                try:
                    return json.loads(block.input)
                except (TypeError, ValueError):
                    return None
        return None

    return _call


def build_default_classifier() -> TransactionClassifier:
    """Construct the classifier the import service uses, gated on the environment.

    AI is enabled only when an ``ANTHROPIC_API_KEY`` is present AND
    ``BUD_AI_CATEGORIZE`` is not explicitly disabled. Setting
    ``BUD_AI_CATEGORIZE=0`` (or ``false``/``no``/``off``) force-disables it even
    when a key exists. The model id can be overridden with
    ``BUD_AI_CATEGORIZE_MODEL``. When disabled, the returned classifier is a
    pure no-op and never touches the network.
    """
    flag = os.environ.get(ENABLE_ENV)
    if flag is not None and flag.strip().lower() in {"0", "false", "no", "off", ""}:
        return TransactionClassifier(None)

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        return TransactionClassifier(None)

    llm_call = _anthropic_llm_call(api_key)
    model = os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    return TransactionClassifier(llm_call, model=model)
