"""Pruebas de la fábrica de proveedores de ticketing."""

from __future__ import annotations

import pytest

from backend.config import Settings
from backend.ticketing.demo import DemoProvider
from backend.ticketing.factory import get_provider
from backend.ticketing.invgate import InvGateProvider
from backend.ticketing.simulated import SimulatedProvider


def test_default_provider_is_demo() -> None:
    assert isinstance(get_provider(Settings()), DemoProvider)


def test_simulated_provider() -> None:
    settings = Settings()
    settings = settings.__class__(**{**settings.__dict__, "ticketing_provider": "simulated"})
    assert isinstance(get_provider(settings), SimulatedProvider)


def test_invgate_provider_requires_credentials() -> None:
    settings = Settings()
    settings = settings.__class__(**{**settings.__dict__, "ticketing_provider": "invgate"})
    with pytest.raises(ValueError):
        get_provider(settings)


def test_invgate_provider_with_credentials() -> None:
    settings = Settings()
    settings = settings.__class__(
        **{
            **settings.__dict__,
            "ticketing_provider": "invgate",
            "invgate_base_url": "https://demo.invgate.net",
            "invgate_api_token": "token",
        }
    )
    assert isinstance(get_provider(settings), InvGateProvider)
