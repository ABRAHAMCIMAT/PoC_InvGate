"""Pruebas del audit trail."""

from __future__ import annotations

import json

from backend.security.audit import AuditLog


def test_audit_records_redacted(tmp_path) -> None:
    path = str(tmp_path / "audit.jsonl")
    log = AuditLog(path)
    log.record("ticket.created", "admin", {"email": "juan@x.com", "phone": "+52 55 1234 5678"})
    with open(path, encoding="utf-8") as fh:
        entry = json.loads(fh.readline())
    assert entry["event"] == "ticket.created"
    assert entry["actor"] == "admin"
    assert "[EMAIL]" in entry["data"]
    assert "[PHONE]" in entry["data"]
    assert "juan@x.com" not in entry["data"]
