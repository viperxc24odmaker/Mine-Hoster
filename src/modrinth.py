from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

API = "https://api.modrinth.com/v2"
USER_AGENT = "MineHoster/2.1"
SUPPORTED = {"paper", "fabric", "forge", "neoforge"}

class ModrinthError(RuntimeError): pass


def _request_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))
    except Exception as exc: raise ModrinthError(f"Modrinth request failed: {exc}") from exc


def _project_type(loader: str) -> str:
    return "mod" if loader in {"fabric", "forge", "neoforge"} else "plugin"


def _facet_json(project_type: str, version: str, loader: str) -> str:
    facets = [[f"project_type:{project_type}"]]
    if version: facets.append([f"versions:{version}"])
    if loader in SUPPORTED: facets.append([f"categories:{loader}"])
    return json.dumps(facets, separators=(",", ":"))


class ModrinthClient:
    def search(self, query="", minecraft_version="", loader="", limit=20):
        if loader in {"purpur", "spigot", "bukkit"}: raise ModrinthError("That server platform is intentionally not supported by MineHoster.")
        params = {"query": query, "facets": _facet_json(_project_type(loader), minecraft_version, loader), "limit": str(max(1, min(100, limit))), "index": "relevance"}
        data = _request_json(f"{API}/search?{urllib.parse.urlencode(params)}")
        return data.get("hits", []) if isinstance(data, dict) else []

    def project_versions(self, project_id, minecraft_version="", loader=""):
        params = {}
        if minecraft_version: params["game_versions"] = json.dumps([minecraft_version])
        if loader in SUPPORTED: params["loaders"] = json.dumps([loader])
        q = f"?{urllib.parse.urlencode(params)}" if params else ""
        data = _request_json(f"{API}/project/{urllib.parse.quote(project_id, safe='')}/version{q}")
        return data if isinstance(data, list) else []

    def choose_version(self, project_id, minecraft_version, loader=""):
        versions = self.project_versions(project_id, minecraft_version, loader)
        compatible = [v for v in versions if minecraft_version in (v.get("game_versions") or []) and (not loader or loader in (v.get("loaders") or []))]
        stable = [v for v in compatible if v.get("version_type", "release") == "release"]
        return (stable or compatible or versions)[0] if (stable or compatible or versions) else None

    def version(self, version_id): return _request_json(f"{API}/version/{urllib.parse.quote(version_id, safe='')}")

    def download_version(self, version, destination: Path, progress_cb: Optional[Callable] = None) -> Path:
        files = version.get("files") or []
        primary = next((f for f in files if f.get("primary")), None) or next((f for f in files if str(f.get("filename", "")).lower().endswith(".jar")), None)
        if not primary or not primary.get("url"): raise ModrinthError("No downloadable JAR was returned by Modrinth.")
        filename = Path(primary.get("filename", "plugin.jar")).name
        if not filename.lower().endswith(".jar"): raise ModrinthError("Refusing a non-JAR server artifact.")
        destination.mkdir(parents=True, exist_ok=True); final = destination / filename; part = destination / f".{filename}.part"
        req = urllib.request.Request(primary["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as out:
                total = int(r.headers.get("Content-Length", 0) or 0); done = 0
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk: break
                    out.write(chunk); done += len(chunk)
                    if progress_cb: progress_cb(done, total, filename)
            if part.stat().st_size < 1024: raise ModrinthError("Downloaded artifact is unexpectedly small.")
            part.replace(final); return final
        except Exception:
            part.unlink(missing_ok=True); raise

    def install_version(self, version, plugins_dir: Path, progress_cb=None, installed=None, depth=0, minecraft_version="", loader=""):
        if depth > 16: raise ModrinthError("Dependency chain exceeded the safety limit.")
        installed = installed if installed is not None else set(); key = version.get("id") or version.get("project_id")
        if key in installed: return []
        installed.add(key); files = []
        game_version = minecraft_version or ((version.get("game_versions") or [""])[0])
        active_loader = loader or ((version.get("loaders") or [""])[0])
        for dep in version.get("dependencies") or []:
            if dep.get("dependency_type") != "required": continue
            dep_version = None
            if dep.get("version_id"):
                try: dep_version = self.version(dep["version_id"])
                except ModrinthError: dep_version = None
            if dep_version is None and dep.get("project_id"): dep_version = self.choose_version(dep["project_id"], game_version, active_loader)
            if not dep_version: raise ModrinthError(f"A required dependency could not be matched to Minecraft {game_version} / {active_loader}.")
            files.extend(self.install_version(dep_version, plugins_dir, progress_cb, installed, depth + 1, game_version, active_loader))
        files.append(self.download_version(version, plugins_dir, progress_cb)); return files


def installed_plugin_names(plugins_dir: Path) -> set[str]:
    return {p.name.lower() for p in plugins_dir.iterdir() if p.is_file() and p.suffix.lower() == ".jar"} if plugins_dir.exists() else set()
