"""Small Flet components shared by the redesigned MineHoster UI."""
from __future__ import annotations

import flet as ft
from .ui_theme import COLORS, RADIUS, SPACING, status_color


def status_badge(status: str) -> ft.Container:
    label = (status or "offline").upper()
    return ft.Container(
        content=ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=COLORS["text"]),
        bgcolor=status_color(status),
        border_radius=RADIUS["sm"],
        padding=ft.padding.symmetric(horizontal=SPACING["sm"], vertical=SPACING["xs"]),
    )


def section_title(title: str, subtitle: str | None = None) -> ft.Column:
    items = [ft.Text(title, size=22, weight=ft.FontWeight.W_700, color=COLORS["text"])]
    if subtitle:
        items.append(ft.Text(subtitle, size=12, color=COLORS["subtext"]))
    return ft.Column(items, spacing=4)
