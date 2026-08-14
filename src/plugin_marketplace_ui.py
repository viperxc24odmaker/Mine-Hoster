"""Pure presentation helpers for Modrinth marketplace cards."""
from __future__ import annotations

from typing import Any
from .plugin_utils import dependency_report, project_icon


def project_summary(project: dict[str, Any], installed_project_ids: set[str]) -> dict[str, Any]:
    report = dependency_report(project, installed_project_ids)
    return {
        "id": project.get("project_id") or project.get("id"),
        "name": project.get("title") or project.get("name") or "Unknown project",
        "description": project.get("description") or "No description available.",
        "icon_url": project_icon(project),
        "downloads": int(project.get("downloads") or 0),
        "missing_dependencies": list(report.missing),
        "dependency_count": len(report.required),
    }
