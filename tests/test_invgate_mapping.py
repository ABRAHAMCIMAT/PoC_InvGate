"""Pruebas del mapeo de campos y valores."""

from __future__ import annotations

from backend.invgate.mapping import FieldMapper, ValueMapper
from backend.invgate.models import Incident


def test_field_mapper_default_identity() -> None:
    mapper = FieldMapper()
    assert mapper.to_invgate("title") == "title"
    assert mapper.from_invgate("title") == "title"


def test_field_mapper_custom() -> None:
    mapper = FieldMapper('{"title": "subject", "description": "details"}')
    assert mapper.to_invgate("title") == "subject"
    assert mapper.from_invgate("subject") == "title"


def test_field_mapper_invalid_json_ignored() -> None:
    mapper = FieldMapper("no-json")
    assert mapper.to_invgate("title") == "title"


def test_field_mapper_payload() -> None:
    mapper = FieldMapper('{"title": "subject"}')
    incident = Incident(title="Hola", description="Mundo")
    payload = mapper.map_payload(incident)
    assert payload["subject"] == "Hola"
    assert payload["description"] == "Mundo"
    assert "id" not in payload


def test_value_mapper() -> None:
    mapper = ValueMapper('{"priority": {"alta": "high", "media": "medium"}}')
    assert mapper.to_invgate("priority", "alta") == "high"
    assert mapper.to_invgate("priority", "desconocida") == "desconocida"
    assert mapper.from_invgate("priority", "high") == "alta"


def test_value_mapper_invalid_json_ignored() -> None:
    mapper = ValueMapper("nope")
    assert mapper.to_invgate("priority", "alta") == "alta"
