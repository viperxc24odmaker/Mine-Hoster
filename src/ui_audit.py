"""Lightweight runtime UI sanity checks used before constructing major views."""
from __future__ import annotations

from typing import Any


def validate_server_record(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, dict):
        return ["server record is not an object"]
    name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("missing server name")
    status = record.get("status")
    if status is not None and not isinstance(status, str):
        problems.append("server status must be text")
    return problems


def safe_text(value: Any, fallback: str = "—") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback
