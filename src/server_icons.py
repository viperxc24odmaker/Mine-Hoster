import json
from pathlib import Path

ICONS_FILE = Path.home() / ".minehoster" / "server_icons.json"
DEFAULT_ICON = "none"

ICON_CHOICES = {
    "none": "✕",
    "grass": "🌱",
    "diamond": "💎",
    "sword": "⚔️",
    "castle": "🏰",
    "nether": "🔥",
    "end": "👁️",
    "stone": "🧱",
    "survival": "🌲",
    "redstone": "🔴",
    "creeper": "💚",
    "dragon": "🐉",
    "star": "⭐",
}


def _load():
    try:
        if ICONS_FILE.exists():
            data = json.loads(ICONS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        pass
    return {}


def get_icon(name: str) -> str:
    key = _load().get(name, DEFAULT_ICON)
    return ICON_CHOICES.get(key, ICON_CHOICES[DEFAULT_ICON])


def get_icon_key(name: str) -> str:
    key = _load().get(name, DEFAULT_ICON)
    return key if key in ICON_CHOICES else DEFAULT_ICON


def set_icon(name: str, key: str) -> None:
    if key not in ICON_CHOICES:
        key = DEFAULT_ICON
    ICONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _load()
    data[name] = key
    ICONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def delete_icon(name: str) -> None:
    data = _load()
    if name in data:
        data.pop(name, None)
        ICONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
