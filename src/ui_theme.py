"""Shared MineHoster visual language for consistent clean UI surfaces."""
from __future__ import annotations

COLORS = {
    "bg": "#0B0F14",
    "surface": "#111820",
    "card": "#151E28",
    "card_hover": "#1A2632",
    "border": "#263442",
    "text": "#F4F7FA",
    "subtext": "#93A4B5",
    "accent": "#5EE6A8",
    "accent_alt": "#72A7FF",
    "danger": "#FF6B7A",
    "warning": "#FFC857",
}

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
RADIUS = {"sm": 8, "md": 12, "lg": 16}


def status_color(status: str) -> str:
    status = (status or "").lower()
    if status in {"online", "running", "ready"}:
        return COLORS["accent"]
    if status in {"starting", "stopping", "installing", "downloading"}:
        return COLORS["warning"]
    if status in {"error", "failed"}:
        return COLORS["danger"]
    return COLORS["subtext"]
