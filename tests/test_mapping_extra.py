"""Pruebas adicionales del mapeo."""

from __future__ import annotations

from backend.invgate.mapping import FieldMapper, ValueMapper


def test_field_mapper_from_invgate_unknown() -> None:
    mapper = FieldMapper('{"title": "subject"}')
    assert mapper.from_invgate("unknown") == "unknown"


def test_value_mapper_from_invgate() -> None:
    mapper = ValueMapper('{"priority": {"alta": "high"}}')
    assert mapper.from_invgate("priority", "high") == "alta"
    assert mapper.from_invgate("priority", "nope") == "nope"


def test_value_mapper_non_dict_ignored() -> None:
    mapper = ValueMapper('{"priority": "not-a-dict"}')
    assert mapper.to_invgate("priority", "alta") == "alta"
