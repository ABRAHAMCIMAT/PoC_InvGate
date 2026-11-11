"""Pruebas del proveedor demo en memoria."""

from __future__ import annotations

import pytest

from backend.invgate.models import Incident
from backend.ticketing.demo import DemoProvider


def test_demo_crud() -> None:
    provider = DemoProvider()
    created = provider.create_incident(Incident(title="Problema"))
    assert created.id is not None
    assert created.number == created.id

    fetched = provider.get_incident(created.id)
    assert fetched.title == "Problema"

    updated = provider.update_incident(created.id, Incident(title="Problema 2"))
    assert updated.title == "Problema 2"

    comment = provider.add_comment(created.id, "Nota")
    assert comment.body == "Nota"
    assert comment.incident_id == created.id

    assert len(provider.list_incidents()) == 1


def test_demo_get_missing_raises() -> None:
    provider = DemoProvider()
    with pytest.raises(KeyError):
        provider.get_incident("DEMO-9999")
