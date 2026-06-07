"""Smoke tests for the API schema layer (backend.schemas).

These verify the Pydantic v2 models construct/validate and round-trip cleanly,
and that the core domain dataclasses map onto them by field name (so the API
layer stays in sync with src/).
"""

from backend import schemas
from src.budget.engine import BudgetState as EngineBudgetState, CategoryState as EngineCategoryState
from src.imports.service import ImportResult as EngineImportResult


def test_category_state_round_trips():
    cs = schemas.CategoryState(
        id="abc", group="Bills", name="Rent",
        assigned=100_000, activity=-50_000, available=50_000,
    )
    assert cs.assigned == 100_000
    assert schemas.CategoryState(**cs.model_dump()) == cs


def test_budget_state_nests_categories():
    bs = schemas.BudgetState(
        month="2026-06-01", ready_to_assign=10_000, income_month=2000,
        income_total=5000, assigned_total=3000,
        categories=[schemas.CategoryState(
            id="c1", group="Needs", name="Groceries",
            assigned=1000, activity=-200, available=800,
        )],
    )
    assert bs.categories[0].available == 800


def test_engine_dataclasses_map_to_schemas():
    """The engine's CategoryState/BudgetState fields are a subset of the schema."""
    engine_cat_fields = set(EngineCategoryState.__dataclass_fields__)
    assert engine_cat_fields <= set(schemas.CategoryState.model_fields)

    engine_budget_fields = set(EngineBudgetState.__dataclass_fields__)
    assert engine_budget_fields <= set(schemas.BudgetState.model_fields)

    engine_import_fields = set(EngineImportResult.__dataclass_fields__)
    assert engine_import_fields <= set(schemas.ImportResult.model_fields)


def test_assign_and_move_requests():
    a = schemas.AssignRequest(category_id="c1", amount=25_000)
    assert a.month is None
    m = schemas.MoveRequest(from_id="c1", to_id="c2", amount=5_000, month="2026-06-01")
    assert m.amount == 5_000


def test_import_result_defaults():
    r = schemas.ImportResult(filename="stmt.qfx")
    assert r.imported == 0 and r.duplicates == 0 and r.already_imported_file is False


def test_rule_defaults():
    r = schemas.Rule(id=1, pattern="WHOLE FOODS", category_id="c1")
    assert r.match_field == "payee" and r.match_type == "contains" and r.priority == 100
