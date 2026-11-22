"""Guards the "full exact amounts" contract (UAT-011): every money value the
API sends is an integer in minor units (D-10), never a float and never a
pre-formatted string, so clients can show exact amounts and never need to
round. Walks the generated OpenAPI schema so a new field is checked too."""

from __future__ import annotations

from app.main import app

# Fields that are legitimately not money, with the reason.
_ALLOWED_NUMBERS = {
    "closing_balance_delta_pct",  # a percentage, not an amount
}


def _properties() -> list[tuple[str, str, dict]]:
    schemas = app.openapi()["components"]["schemas"]
    return [
        (model, name, prop)
        for model, schema in schemas.items()
        for name, prop in schema.get("properties", {}).items()
    ]


def _types(prop: dict) -> set[str]:
    types = {prop["type"]} if "type" in prop else set()
    for option in prop.get("anyOf", []) + prop.get("oneOf", []):
        types |= _types(option)
    return types


def test_every_minor_unit_field_is_an_integer() -> None:
    offenders = [
        f"{model}.{name}: {sorted(_types(prop))}"
        for model, name, prop in _properties()
        if name.endswith("_minor") and not _types(prop) <= {"integer", "null"}
    ]
    assert offenders == []


def test_no_response_or_request_field_is_a_float_unless_allowed() -> None:
    offenders = [
        f"{model}.{name}"
        for model, name, prop in _properties()
        if "number" in _types(prop) and name not in _ALLOWED_NUMBERS
    ]
    assert offenders == []


def test_there_are_minor_unit_fields_to_check() -> None:
    # Guards the guard: an empty list above would pass vacuously.
    assert sum(1 for _, name, _ in _properties() if name.endswith("_minor")) >= 10
