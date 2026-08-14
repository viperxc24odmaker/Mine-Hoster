"""Safe icon selection for marketplace/server cards."""
from __future__ import annotations

from typing import Any


def icon_url(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("https://") or value.startswith("http://"):
            return value
    return None


def project_icon_or_default(project: dict[str, Any]) -> str | None:
    return icon_url(project.get("icon_url"))
