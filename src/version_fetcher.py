import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
PAPER_V3 = "https://fill.papermc.io/v3/projects/paper"
PAPER_V2 = "https://api.papermc.io/v2/projects/paper"
FABRIC_META = "https://meta.fabricmc.net/v2"
FORGE_MAVEN = "https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json"
BDS_LATEST = "https://aka.ms/MinecraftBDS"
USER_AGENT = "MineHoster/2.0 (https://github.com/viperxc24odmaker/Mine-Hoster)"
MIN_VERSION = "1.12"


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _version_tuple(v: str) -> tuple:
    parts = []
    for part in v.replace("-", ".").split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_at_least(version: str, minimum: str) -> bool:
    return _version_tuple(version) >= _version_tuple(minimum)


def _stable_versions(values):
    return sorted({v for v in values if v and "-" not in v and _is_at_least(v, MIN_VERSION)}, key=_version_tuple, reverse=True)


@lru_cache(maxsize=1)
def fetch_vanilla_versions() -> dict[str, str]:
    data = _http_get(MANIFEST_URL)
    releases = [v for v in data.get("versions", []) if v.get("type") == "release" and _is_at_least(v.get("id", ""), MIN_VERSION)]

    def resolve(entry):
        try:
            data = _http_get(entry["url"])
            return entry["id"], data.get("downloads", {}).get("server", {}).get("url")
        except Exception:
            return entry["id"], None

    result = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(resolve, entry) for entry in releases]):
            version, url = future.result()
            if url:
                result[version] = url
    return dict(sorted(result.items(), key=lambda item: _version_tuple(item[0]), reverse=True))


def _paper_v3() -> dict[str, str]:
    project = _http_get(PAPER_V3)
    versions = []
    for group in project.get("versions", {}).values():
        versions.extend(group)
    versions = _stable_versions(versions)

    def resolve(version):
        try:
            builds = _http_get(f"{PAPER_V3}/versions/{version}/builds")
            for build in builds if isinstance(builds, list) else []:
                if build.get("channel") != "STABLE":
                    continue
                url = build.get("downloads", {}).get("server:default", {}).get("url")
                if url:
                    return version, url
        except Exception:
            pass
        return version, None

    result = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(resolve, version) for version in versions]):
            version, url = future.result()
            if url:
                result[version] = url
    return dict(sorted(result.items(), key=lambda item: _version_tuple(item[0]), reverse=True))


def _paper_v2() -> dict[str, str]:
    data = _http_get(PAPER_V2)
    result = {}
    for version in data.get("versions", []):
        if not _is_at_least(version, MIN_VERSION):
            continue
        try:
            builds = _http_get(f"{PAPER_V2}/versions/{version}/builds").get("builds", [])
            stable = [b for b in builds if b.get("channel", "STABLE") == "STABLE"]
            candidates = stable or builds
            if not candidates:
                continue
            latest = max(candidates, key=lambda b: int(b.get("build", 0)))
            download = latest.get("downloads", {}).get("application", {})
            url = download.get("url")
            if not url and latest.get("build") and download.get("name"):
                url = f"{PAPER_V2}/versions/{version}/builds/{latest['build']}/downloads/{download['name']}"
            if url:
                result[version] = url
        except Exception:
            continue
    return dict(sorted(result.items(), key=lambda item: _version_tuple(item[0]), reverse=True))


@lru_cache(maxsize=1)
def fetch_paper_versions() -> dict[str, str]:
    try:
        result = _paper_v3()
        if result:
            return result
    except Exception:
        pass
    return _paper_v2()


@lru_cache(maxsize=1)
def fetch_fabric_versions() -> dict[str, str]:
    game_versions = _http_get(f"{FABRIC_META}/versions/game")
    loaders = _http_get(f"{FABRIC_META}/versions/loader")
    installers = _http_get(f"{FABRIC_META}/versions/installer")
    if not loaders or not installers:
        return {}
    latest_loader = loaders[0]["version"]
    latest_installer = installers[0]["version"]
    result = {}
    for gv in game_versions:
        version = gv.get("version", "")
        if not gv.get("stable") or not _is_at_least(version, "1.14"):
            continue
        result[version] = f"{FABRIC_META}/versions/loader/{version}/{latest_loader}/{latest_installer}/server/jar"
    return dict(sorted(result.items(), key=lambda item: _version_tuple(item[0]), reverse=True))


@lru_cache(maxsize=1)
def fetch_forge_versions() -> dict[str, str]:
    data = _http_get(FORGE_MAVEN)
    result = {}
    for mc_version, forge_builds in data.items():
        if not _is_at_least(mc_version, MIN_VERSION) or not forge_builds:
            continue
        latest = forge_builds[-1]
        full = f"{mc_version}-{latest}"
        result[mc_version] = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{full}/forge-{full}-installer.jar"
    return dict(sorted(result.items(), key=lambda item: _version_tuple(item[0]), reverse=True))


def fetch_bedrock_versions() -> dict[str, str]:
    # The official aka.ms redirect is maintained by Microsoft/Mojang and resolves to
    # the current stable BDS archive. Keep a known-good historical fallback for
    # temporary redirect/network failures.
    return {
        "Latest": BDS_LATEST,
        "1.21.51": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.51.02.zip",
        "1.21.44": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.44.01.zip",
        "1.21.40": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.40.02.zip",
        "1.21.30": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.30.03.zip",
        "1.21.20": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.20.01.zip",
        "1.21.10": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.10.03.zip",
        "1.21.0": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.0.03.zip",
        "1.20.80": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.20.80.05.zip",
        "1.20.72": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.20.72.01.zip",
    }


def get_versions_for_loader(loader: str) -> dict[str, str]:
    fetchers = {
        "vanilla": fetch_vanilla_versions,
        "paper": fetch_paper_versions,
        "fabric": fetch_fabric_versions,
        "forge": fetch_forge_versions,
        "bedrock": fetch_bedrock_versions,
    }
    fetcher = fetchers.get(loader)
    return fetcher() if fetcher else {}


def clear_cache():
    fetch_vanilla_versions.cache_clear()
    fetch_paper_versions.cache_clear()
    fetch_fabric_versions.cache_clear()
    fetch_forge_versions.cache_clear()
