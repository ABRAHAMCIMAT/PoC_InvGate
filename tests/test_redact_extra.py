"""Pruebas adicionales de redaccion de PII."""

from __future__ import annotations

from backend.security.redact import redact


def test_redact_email() -> None:
    assert redact("contacta a ana@corp.com hoy") == "contacta a [EMAIL] hoy"


def test_redact_phone() -> None:
    assert redact("llama al 5551234567") == "llama al [PHONE]"


def test_redact_clean_text_unchanged() -> None:
    assert redact("sin datos personales") == "sin datos personales"


def test_redact_is_linear_on_hostile_input() -> None:
    """Las regex no deben retroceder: entradas de 100k caracteres se procesan al instante."""
    import time

    hostile = ["a" * 50_000 + "@" + "b-" * 50_000, "1 " * 100_000, "a." * 30_000 + "@x"]
    start = time.perf_counter()
    for text in hostile:
        redact(text)
    assert time.perf_counter() - start < 2.0


def test_redact_keeps_surrounding_text() -> None:
    out = redact("tel +52 55 1234 5678 fin; otro 555-123-4567. correo a.b+c@x.co.mx!")
    assert out == "tel [PHONE] fin; otro [PHONE]. correo [EMAIL]!"


def test_redact_ignores_dates_and_short_numbers() -> None:
    text = "versión 1.2.3, fecha 2026-11-12, IP 10.0.0.1, ticket DEMO-0001, ---------- fin"
    assert redact(text) == text
