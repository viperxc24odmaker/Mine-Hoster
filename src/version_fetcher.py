import json
import urllib.request
from functools import lru_cache

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
PAPER_API = "https://api.papermc.io/v2/projects/paper"
FABRIC_META = "https://meta.fabricmc.net/v2"
FORGE_MAVEN = "https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json"

MIN_VERSION = "1.12"


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "MineHoster/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _version_tuple(v: str) -> tuple:
    parts = []
    for p in v.replace("-", ".").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_at_least(version: str, minimum: str) -> bool:
    return _version_tuple(version) >= _version_tuple(minimum)


@lru_cache(maxsize=1)
def fetch_vanilla_versions() -> dict[str, str]:
    data = _http_get(MANIFEST_URL)
    result = {}
    for v in data["versions"]:
        if v["type"] != "release":
            continue
        vid = v["id"]
        if not _is_at_least(vid, MIN_VERSION):
            continue
        try:
            vdata = _http_get(v["url"])
            url = vdata.get("downloads", {}).get("server", {}).get("url")
            if url:
                result[vid] = url
        except Exception:
            continue
    return dict(sorted(result.items(), key=lambda x: _version_tuple(x[0]), reverse=True))


@lru_cache(maxsize=1)
def fetch_paper_versions() -> dict[str, str]:
    data = _http_get(PAPER_API)
    versions = data.get("versions", [])
    result = {}
    for ver in versions:
        if not _is_at_least(ver, MIN_VERSION):
            continue
        try:
            builds_data = _http_get(f"{PAPER_API}/versions/{ver}/builds")
            builds = builds_data.get("builds", [])
            if not builds:
                continue
            latest = builds[-1]
            build_num = latest["build"]
            filename = latest["downloads"]["application"]["name"]
            url = f"{PAPER_API}/versions/{ver}/builds/{build_num}/downloads/{filename}"
            result[ver] = url
        except Exception:
            continue
    return dict(sorted(result.items(), key=lambda x: _version_tuple(x[0]), reverse=True))


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
        if not gv.get("stable"):
            continue
        vid = gv["version"]
        if not _is_at_least(vid, "1.14"):  # Fabric didn't exist before 1.14
            continue
        url = f"{FABRIC_META}/versions/loader/{vid}/{latest_loader}/{latest_installer}/server/jar"
        result[vid] = url
    return dict(sorted(result.items(), key=lambda x: _version_tuple(x[0]), reverse=True))


@lru_cache(maxsize=1)
def fetch_forge_versions() -> dict[str, str]:
    data = _http_get(FORGE_MAVEN)
    result = {}
    for mc_ver, forge_builds in data.items():
        if not _is_at_least(mc_ver, MIN_VERSION):
            continue
        if not forge_builds:
            continue
        latest = forge_builds[-1]
        forge_full = f"{mc_ver}-{latest}"
        url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{forge_full}/forge-{forge_full}-installer.jar"
        result[mc_ver] = url
    return dict(sorted(result.items(), key=lambda x: _version_tuple(x[0]), reverse=True))


def fetch_bedrock_versions() -> dict[str, str]:
    # Bedrock server doesn't have a public version API, we use the latest known stable
    return {
        "1.21.51": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.51.02.zip",
        "1.21.44": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.44.01.zip",
        "1.21.40": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.40.01.zip",
        "1.21.30": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.30.03.zip",
        "1.21.20": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.20.01.zip",
        "1.21.10": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.10.03.zip",
        "1.21.0":  "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.0.03.zip",
        "1.20.80": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.20.80.05.zip",
        "1.20.72": "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.20.72.01.zip",
    }


def get_versions_for_loader(loader: str) -> dict[str, str]:
    if loader == "vanilla":
        return fetch_vanilla_versions()
    elif loader == "paper":
        return fetch_paper_versions()
    elif loader == "fabric":
        return fetch_fabric_versions()
    elif loader == "forge":
        return fetch_forge_versions()
    elif loader == "bedrock":
        return fetch_bedrock_versions()
    return {}


def clear_cache():
    fetch_vanilla_versions.cache_clear()
    fetch_paper_versions.cache_clear()
    fetch_fabric_versions.cache_clear()
    fetch_forge_versions.cache_clear()
