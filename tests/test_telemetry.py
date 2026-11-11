"""Pruebas de telemetría JSONL."""

from __future__ import annotations

import json
import os

from backend.observability.telemetry import Telemetry


def test_telemetry_writes_jsonl(tmp_path) -> None:
    path = str(tmp_path / "telemetry.jsonl")
    tel = Telemetry(path)
    tel.emit("chat", conversation_id="abc", message="hola juan@x.com")
    with open(path, encoding="utf-8") as fh:
        line = json.loads(fh.readline())
    assert line["event"] == "chat"
    assert line["conversation_id"] == "abc"
    assert "[EMAIL]" in line["message"]
