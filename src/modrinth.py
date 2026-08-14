"""Small, dependency-free Modrinth API client used by MineHoster.

The service deliberately uses urllib instead of adding another runtime dependency so
PyInstaller builds remain simple. Downloads are streamed to .part files and promoted
only after the HTTP request completes successfully.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

API = "https://api.modrinth.com/v2"
USER_AGENT = "MineHoster/2.0 (https://github.com/viperxc24odmaker/Mine-Hoster)"


class ModrinthError(RuntimeError):
    pass


def _request_json(url: str, timeout: int = 30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ModrinthError(f"Modrinth request failed: {exc}") from exc


def _facet_json(project_type: str = "plugin", minecraft_version: str = "", loader: str = "") -> str:
    facets = [[f"project_type:{project_type}"]]
    if minecraft_version:
        facets.append([f"versions:{minecraft_version}"])
    if loader and loader not in {"paper", "spigot", "bukkit", "purpur", "velocity", "fabric", "forge", "neoforge"}:
        loader = ""
    if loader:
        facets.append([f"categories:{loader}"])
    return json.dumps(facets, separators=(",", ":"))


class ModrinthClient:
    def search(self, query: str = "", minecraft_version: str = "", loader: str = "", limit: int = 20):
        params = {
            "query": query,
            "facets": _facet_json("plugin", minecraft_version, loader),
            "limit": str(max(1, min(100, limit))),
            "index": "relevance",
        }
        url = f"{API}/search?{urllib.parse.urlencode(params)}"
        data = _request_json(url)
        return data.get("hits", []) if isinstance(data, dict) else []

    def project_versions(self, project_id: str, minecraft_version: str = "", loader: str = ""):
        params = {"game_versions": json.dumps([minecraft_version])} if minecraft_version else {}
        if loader:
            params["loaders"] = json.dumps([loader])
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        data = _request_json(f"{API}/project/{urllib.parse.quote(project_id, safe='')}/version{query}")
        return data if isinstance(data, list) else []

    def choose_version(self, project_id: str, minecraft_version: str, loader: str = ""):
        versions = self.project_versions(project_id, minecraft_version, loader)
        if not versions:
            return None
        stable = [v for v in versions if not v.get("version_type") or v.get("version_type") == "release"]
        candidates = stable or versions
        return candidates[0]

    def version(self, version_id: str):
        return _request_json(f"{API}/version/{urllib.parse.quote(version_id, safe='')}")

    def download_version(
        self,
        version: dict,
        destination: Path,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> Path:
        files = version.get("files") or []
        primary = next((f for f in files if f.get("primary")), None)
        if primary is None:
            primary = next((f for f in files if str(f.get("filename", "")).lower().endswith(".jar")), None)
        if not primary or not primary.get("url"):
            raise ModrinthError("This Modrinth version has no downloadable JAR file.")

        filename = Path(primary.get("filename") or "plugin.jar").name
        if not filename.lower().endswith(".jar"):
            raise ModrinthError("Modrinth returned a non-JAR plugin artifact.")
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
                raise ModrinthError("Downloaded plugin is unexpectedly small.")
            part_path.replace(final_path)
            return final_path
        except Exception:
            part_path.unlink(missing_ok=True)
            raise

    def install_version(
        self,
        version: dict,
        plugins_dir: Path,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        installed: Optional[set[str]] = None,
        depth: int = 0,
    ) -> list[Path]:
        if depth > 16:
            raise ModrinthError("Plugin dependency chain is too deep; installation was stopped for safety.")
        installed = installed if installed is not None else set()
        project_id = version.get("project_id")
        version_id = version.get("id")
        key = version_id or project_id
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
                    dep_version = None
            if dep_version is None and dependency.get("project_id"):
                dep_version = self.choose_version(dependency["project_id"], version.get("game_versions", [""])[0] if version.get("game_versions") else "")
            if dep_version:
                installed_files.extend(self.install_version(dep_version, plugins_dir, progress_cb, installed, depth + 1))

        installed_files.append(self.download_version(version, plugins_dir, progress_cb))
        return installed_files


def installed_plugin_names(plugins_dir: Path) -> set[str]:
    if not plugins_dir.exists():
        return set()
    return {p.name.lower() for p in plugins_dir.iterdir() if p.is_file() and p.suffix.lower() == ".jar"}
