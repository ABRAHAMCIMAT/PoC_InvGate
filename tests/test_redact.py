"""Pruebas de redacción de PII."""

from __future__ import annotations

from backend.security.redact import redact


def test_redact_email() -> None:
    assert redact("contacta a juan@correo.com ya") == "contacta a [EMAIL] ya"


def test_redact_phone() -> None:
    assert "[PHONE]" in redact("llama al 55 1234 5678")


def test_redact_plain() -> None:
    assert redact("sin datos sensibles") == "sin datos sensibles"
