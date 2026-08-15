from __future__ import annotations

import re
import threading
import time
import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS


class PlayersViewV2:
    def __init__(self, app):
        self.app = app; self.sm = ServerManager.get(); self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.tab = "online"; self.online = []; self.rows = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO); self.status = ft.Text("", color=COLORS["subtext"], size=12); self.input = ft.TextField(label="Player name", width=240)
        if self.selected: self.sm.register_console_callback(self.selected, self._console)

    def build(self):
        servers = self.sm.get_servers(); dd = ft.Dropdown(value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._server, width=220)
        tabs = ft.Tabs(selected_index=["online","whitelist","ops","banned"].index(self.tab), on_change=self._tab, tabs=[ft.Tab(text="Online"), ft.Tab(text="Whitelist"), ft.Tab(text="Operators"), ft.Tab(text="Banned")])
        self._refresh(); return ft.Container(content=ft.Column([ft.Row([ft.Text("Players", size=26, weight=ft.FontWeight.BOLD, color=COLORS["text"]), dd]), tabs, ft.Row([self.input, ft.Button("Add", on_click=self._add), ft.Button("Refresh", on_click=self._query)]), self.status, self.rows], expand=True), padding=28, expand=True)

    def _console(self, line):
        m = re.search(r"There are\s+\d+\s+of a max(?:imum)?\s+\d+\s+players online:\s*(.*)$", line, re.I)
        if not m: m = re.search(r"players online:\s*(.*)$", line, re.I)
        if m:
            names = [x.strip() for x in m.group(1).split(",") if x.strip() and x.strip().lower() not in ("none", "-", "")]
            self.online = names; self._render();

    def _query(self, e=None):
        if not self.selected: return
        if not self.sm.is_running(self.selected): self.status.value = "Start the server to see live players."; self.status.color = COLORS["warning"]; self._safe(); return
        self.status.value = "Refreshing online players..."; self.sm.send_command(self.selected, "list"); self._safe()

    def _refresh(self):
        self.rows.controls.clear()
        if self.tab == "online": values = [(x, "Online") for x in self.online]
        elif self.tab == "whitelist": values = [(x.get("name","Unknown"), "Remove") for x in self.sm.get_whitelist(self.selected)]
        elif self.tab == "ops": values = [(x.get("name","Unknown"), "Remove") for x in self.sm.get_ops(self.selected)]
        else: values = [(x.get("name","Unknown"), "Unban") for x in self.sm.get_banned_players(self.selected)]
        if not values: self.rows.controls.append(ft.Text("No players found.", color=COLORS["subtext"]))
        for name, action in values:
            btn = ft.Button(action, disabled=action == "Online", on_click=lambda e, n=name: self._remove(n))
            self.rows.controls.append(ft.Container(content=ft.Row([ft.Text("●", color=COLORS["accent2"] if action == "Online" else COLORS["muted"]), ft.Text(name, color=COLORS["text"], expand=True), btn]), bgcolor=COLORS["card"], border_radius=10, padding=12))

    def _remove(self, name):
        if self.tab == "whitelist": self.sm.remove_whitelist(self.selected, name)
        elif self.tab == "ops": self.sm.remove_op(self.selected, name)
        elif self.tab == "banned": self.sm.unban_player(self.selected, name)
        self._refresh(); self._safe()

    def _add(self, e):
        name = (self.input.value or "").strip()
        if not name or not self.selected or self.tab == "online": return
        if self.tab == "whitelist": self.sm.add_whitelist(self.selected, name)
        elif self.tab == "ops": self.sm.add_op(self.selected, name)
        else: self.sm.ban_player(self.selected, name)
        self.input.value = ""; self.status.value = f"✓ Updated {name}"; self._refresh(); self._safe()

    def _tab(self, e): self.tab = ["online","whitelist","ops","banned"][e.control.selected_index]; self._refresh(); self._safe(); self._query()
    def _server(self, e):
        if self.selected: self.sm.unregister_console_callbacks(self.selected)
        self.selected = e.control.value; self.sm.register_console_callback(self.selected, self._console); self.online = []; self._refresh(); self._query()
    def _render(self): self._refresh(); self._safe()
    def _safe(self):
        try: self.app.page.update()
        except Exception: pass
