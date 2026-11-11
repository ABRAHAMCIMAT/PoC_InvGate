"""Pruebas adicionales de redaccion de PII."""

from __future__ import annotations

from backend.security.redact import redact


def test_redact_email() -> None:
    assert redact("contacta a ana@corp.com hoy") == "contacta a [EMAIL] hoy"


def test_redact_phone() -> None:
    assert redact("llama al 5551234567") == "llama al [PHONE]"


def test_redact_clean_text_unchanged() -> None:
    assert redact("sin datos personales") == "sin datos personales"
