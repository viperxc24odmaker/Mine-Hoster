"""Plugin marketplace helpers: icons, dependency checks, and safe install planning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class DependencyReport:
    required: tuple[str, ...]
    installed: tuple[str, ...]
    missing: tuple[str, ...]


def project_icon(project: dict[str, Any]) -> str | None:
    """Return Modrinth's project icon URL when available."""
    value = project.get("icon_url")
    return value if isinstance(value, str) and value.startswith(("https://", "http://")) else None


def dependency_report(project: dict[str, Any], installed_project_ids: Iterable[str]) -> DependencyReport:
    """Compare required Modrinth dependency project IDs with installed project IDs."""
    installed = {str(x) for x in installed_project_ids}
    required: list[str] = []
    for dep in project.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        if dep.get("dependency_type") == "required" and dep.get("project_id"):
            required.append(str(dep["project_id"]))
    required_unique = tuple(dict.fromkeys(required))
    installed_required = tuple(x for x in required_unique if x in installed)
    missing = tuple(x for x in required_unique if x not in installed)
    return DependencyReport(required=required_unique, installed=installed_required, missing=missing)


def has_missing_dependencies(project: dict[str, Any], installed_project_ids: Iterable[str]) -> bool:
    return bool(dependency_report(project, installed_project_ids).missing)
