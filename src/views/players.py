from __future__ import annotations

import re
import threading
import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS


class PlayersView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.active_tab = "online"
        self.player_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.input_field = ft.TextField(hint_text="Player name...", border_color=COLORS["border"], focused_border_color=COLORS["accent"], color=COLORS["text"], bgcolor=COLORS["surface2"], width=240)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)
        self.online_count = ft.Text("0 online", color=COLORS["accent2"], size=12)
        self.online_players: list[str] = []
        self.waiting_for_list = False

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(content=ft.Text("No servers found.", color=COLORS["subtext"]), padding=32)
        server_dd = ft.Dropdown(value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._on_server_change, border_color=COLORS["border"], focused_border_color=COLORS["accent"], color=COLORS["text"], bgcolor=COLORS["surface2"], width=200)
        tabs = ft.Tabs(selected_index=0, on_change=self._on_tab_change, indicator_color=COLORS["accent"], label_color=COLORS["text"], unselected_label_color=COLORS["subtext"], tabs=[ft.Tab(text="Online"), ft.Tab(text="Whitelist"), ft.Tab(text="Operators"), ft.Tab(text="Banned Players")])
        refresh_btn = ft.ElevatedButton("Refresh Online", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._refresh_online)
        add_btn = ft.ElevatedButton("Add", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._add_player)
        self._refresh_list()
        return ft.Container(content=ft.Column([
            ft.Row([ft.Column([ft.Text("Player Management", size=22, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Live players plus whitelist, operator and ban management.", color=COLORS["subtext"], size=13)], expand=True), server_dd]),
            ft.Row([tabs, ft.Container(expand=True), self.online_count, refresh_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.input_field, add_btn, self.status_text], spacing=12),
            ft.Divider(color=COLORS["border"]),
            self.player_list,
        ], expand=True, scroll=ft.ScrollMode.AUTO), padding=32, expand=True)

    def _refresh_online(self, e=None):
        if not self.selected:
            return
        if not self.sm.is_running(self.selected):
            self.online_players = []
            self.status_text.value = "Start the server to view online players."
            self.status_text.color = COLORS["warning"]
            self._refresh_list()
            return
        self.waiting_for_list = True
        self.status_text.value = "Querying the server..."
        self.status_text.color = COLORS["subtext"]
        self._refresh_list()
        callback = self._capture_console
        self.sm.register_console_callback(self.selected, callback)
        self.sm.send_command(self.selected, "list")
        def timeout():
            threading.Event().wait(2.5)
            self.sm.unregister_console_callbacks(self.selected)
            if self.waiting_for_list:
                self.waiting_for_list = False
                self.status_text.value = "No player-list response received yet."
                self.status_text.color = COLORS["warning"]
                self._refresh_list()
        threading.Thread(target=timeout, daemon=True).start()

    def _capture_console(self, line):
        match = re.search(r"There are\s+(\d+)\s+of a max(?: of)?\s+\d+\s+players online:\s*(.*)$", line, re.IGNORECASE)
        if not match:
            return
        count = int(match.group(1))
        names = [n.strip() for n in match.group(2).split(",") if n.strip()]
        self.online_players = names
        self.online_count.value = f"{count} online"
        self.waiting_for_list = False
        self.sm.unregister_console_callbacks(self.selected)
        self.status_text.value = "✓ Online player list refreshed."
        self.status_text.color = COLORS["accent2"]
        self._refresh_list()

    def _refresh_list(self):
        if not self.selected:
            return
        self.player_list.controls.clear()
        if self.active_tab == "online":
            players = [{"name": n} for n in self.online_players]
            action_label = "Kick"
            action = lambda name: self.sm.send_command(self.selected, f"kick {name} Removed by MineHoster")
        elif self.active_tab == "whitelist":
            players = self.sm.get_whitelist(self.selected); action = lambda name: self.sm.remove_whitelist(self.selected, name); action_label = "Remove"
        elif self.active_tab == "ops":
            players = self.sm.get_ops(self.selected); action = lambda name: self.sm.remove_op(self.selected, name); action_label = "Remove"
        else:
            players = self.sm.get_banned_players(self.selected); action = lambda name: self.sm.unban_player(self.selected, name); action_label = "Unban"
        if not players:
            self.player_list.controls.append(ft.Text("No players here yet", color=COLORS["subtext"], size=13))
        else:
            for p in players:
                name = p.get("name", "Unknown")
                self.player_list.controls.append(self._player_row(name, action_label, action))
        self._safe_update()

    def _player_row(self, name: str, action_label: str, action_fn):
        def do_action(e, n=name):
            action_fn(n)
            self._refresh_list()
        return ft.Container(content=ft.Row([ft.Text("●", color=COLORS["accent2"] if self.active_tab == "online" else COLORS["muted"], size=12), ft.Text(name, color=COLORS["text"], size=13, expand=True), ft.ElevatedButton(action_label, bgcolor=COLORS["danger"], color=COLORS["text"], on_click=do_action)], spacing=12), bgcolor=COLORS["card"], border_radius=8, padding=ft.padding.symmetric(horizontal=16, vertical=12), border=ft.border.all(1, COLORS["border"]))

    def _add_player(self, e):
        name = (self.input_field.value or "").strip()
        if not name or not self.selected or self.active_tab == "online":
            self.status_text.value = "Switch to Whitelist, Operators or Banned Players to add someone."
            self.status_text.color = COLORS["warning"]
            self._safe_update()
            return
        if self.active_tab == "whitelist": self.sm.add_whitelist(self.selected, name)
        elif self.active_tab == "ops": self.sm.add_op(self.selected, name)
        else: self.sm.ban_player(self.selected, name)
        self.input_field.value = ""
        self.status_text.value = f"✓ Added {name}"
        self.status_text.color = COLORS["accent2"]
        self._refresh_list()

    def _on_tab_change(self, e):
        self.active_tab = ["online", "whitelist", "ops", "banned"][e.control.selected_index]
        self._refresh_list()

    def _on_server_change(self, e):
        self.selected = e.control.value
        self.app.selected_server = self.selected
        self.online_players = []
        self._refresh_list()

    def _safe_update(self):
        try:
            self.app.page.update()
        except Exception:
            pass
