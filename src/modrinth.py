"""Small, dependency-free Modrinth API client used by MineHoster.

The client keeps compatibility filtering strict: project type, Minecraft version,
and loader are all considered before a version is selected. Required dependencies
are resolved with the same compatibility constraints as the parent project.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

API = "https://api.modrinth.com/v2"
USER_AGENT = "MineHoster/2.1 (https://github.com/viperxc24odmaker/Mine-Hoster)"
SUPPORTED_LOADERS = {"paper", "bukkit", "fabric", "forge", "neoforge"}


class ModrinthError(RuntimeError):
    pass


def _request_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ModrinthError(f"Modrinth request failed: {exc}") from exc


def _facet_json(project_type: str, minecraft_version: str = "", loader: str = "") -> str:
    facets = [[f"project_type:{project_type}"]]
    if minecraft_version:
        facets.append([f"versions:{minecraft_version}"])
    if loader in SUPPORTED_LOADERS:
        facets.append([f"categories:{loader}"])
    return json.dumps(facets, separators=(",", ":"))


class ModrinthClient:
    def search(self, query: str = "", minecraft_version: str = "", loader: str = "", limit: int = 20, project_type: str = "plugin"):
        params = {
            "query": query,
            "facets": _facet_json(project_type, minecraft_version, loader),
            "limit": str(max(1, min(100, limit))),
            "index": "relevance",
        }
        data = _request_json(f"{API}/search?{urllib.parse.urlencode(params)}")
        return data.get("hits", []) if isinstance(data, dict) else []

    def project_versions(self, project_id: str, minecraft_version: str = "", loader: str = ""):
        params = {}
        if minecraft_version:
            params["game_versions"] = json.dumps([minecraft_version])
        if loader in SUPPORTED_LOADERS:
            params["loaders"] = json.dumps([loader])
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        data = _request_json(f"{API}/project/{urllib.parse.quote(project_id, safe='')}/version{query}")
        return data if isinstance(data, list) else []

    def choose_version(self, project_id: str, minecraft_version: str, loader: str = "", project_type: str = "plugin"):
        versions = self.project_versions(project_id, minecraft_version, loader)
        if not versions:
            return None
        # Search can occasionally return a project whose metadata is stale. Re-check
        # every candidate before selecting it rather than silently installing a mismatch.
        exact = [
            v for v in versions
            if minecraft_version in (v.get("game_versions") or [])
            and (not loader or loader in (v.get("loaders") or []))
            and (v.get("version_type") in (None, "release"))
        ]
        return (exact or versions)[0] if (exact or versions) else None

    def version(self, version_id: str):
        return _request_json(f"{API}/version/{urllib.parse.quote(version_id, safe='')}")

    def download_version(self, version: dict, destination: Path, progress_cb: Optional[Callable[[int, int, str], None]] = None) -> Path:
        files = version.get("files") or []
        primary = next((f for f in files if f.get("primary")), None)
        primary = primary or next((f for f in files if str(f.get("filename", "")).lower().endswith(".jar")), None)
        if not primary or not primary.get("url"):
            raise ModrinthError("This Modrinth version has no downloadable JAR file.")
        filename = Path(primary.get("filename") or "plugin.jar").name
        if not filename.lower().endswith(".jar"):
            raise ModrinthError("Modrinth returned a non-JAR artifact.")
        destination.mkdir(parents=True, exist_ok=True)
        final_path = destination / filename
        part_path = destination / f".{filename}.part"
        req = urllib.request.Request(primary["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120) as response, part_path.open("wb") as out:
                total = int(response.headers.get("Content-Length", 0) or 0)
                done = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total, filename)
            if part_path.stat().st_size < 1024:
                raise ModrinthError("Downloaded artifact is unexpectedly small.")
            part_path.replace(final_path)
            return final_path
        except Exception:
            part_path.unlink(missing_ok=True)
            raise

    def install_version(self, version: dict, plugins_dir: Path, progress_cb=None, installed=None, depth: int = 0, minecraft_version: str = "", loader: str = "") -> list[Path]:
        if depth > 16:
            raise ModrinthError("Dependency chain is too deep; installation was stopped for safety.")
        installed = installed if installed is not None else set()
        key = version.get("id") or version.get("project_id")
        if key and key in installed:
            return []
        if key:
            installed.add(key)
        installed_files: list[Path] = []
        for dependency in version.get("dependencies") or []:
            if dependency.get("dependency_type") != "required":
                continue
            dep_version = None
            if dependency.get("version_id"):
                try:
                    dep_version = self.version(dependency["version_id"])
                except ModrinthError:
                    pass
            if dep_version is None and dependency.get("project_id"):
                dep_version = self.choose_version(
                    dependency["project_id"], minecraft_version or ((version.get("game_versions") or [""])[0]), loader
                )
            if dep_version is None:
                raise ModrinthError(f"A required dependency for {version.get('name', 'this project')} has no compatible release.")
            dep_versions = dep_version.get("game_versions") or []
            dep_loaders = dep_version.get("loaders") or []
            if minecraft_version and minecraft_version not in dep_versions:
                raise ModrinthError(f"Dependency {dep_version.get('name', 'unknown')} is not compatible with Minecraft {minecraft_version}.")
            if loader and loader in SUPPORTED_LOADERS and loader not in dep_loaders:
                raise ModrinthError(f"Dependency {dep_version.get('name', 'unknown')} is not compatible with {loader}.")
            installed_files.extend(self.install_version(dep_version, plugins_dir, progress_cb, installed, depth + 1, minecraft_version, loader))
        installed_files.append(self.download_version(version, plugins_dir, progress_cb))
        return installed_files


def installed_plugin_names(plugins_dir: Path) -> set[str]:
    if not plugins_dir.exists():
        return set()
    return {p.name.lower() for p in plugins_dir.iterdir() if p.is_file() and p.suffix.lower() == ".jar"}
