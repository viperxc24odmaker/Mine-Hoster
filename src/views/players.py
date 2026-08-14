import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS


class PlayersView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.active_tab = "whitelist"
        self.player_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.input_field = ft.TextField(
            hint_text="Player name...",
            border_color=COLORS["border"],
            focused_border_color=COLORS["accent"],
            color=COLORS["text"],
            bgcolor=COLORS["surface2"],
            width=240,
        )
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(
                content=ft.Text("No servers found.", color=COLORS["subtext"]),
                padding=32,
            )

        server_dd = ft.Dropdown(
            value=self.selected,
            options=[ft.dropdown.Option(s.name) for s in servers],
            on_change=self._on_server_change,
            border_color=COLORS["border"],
            focused_border_color=COLORS["accent"],
            color=COLORS["text"],
            bgcolor=COLORS["surface2"],
            width=200,
        )

        tabs = ft.Tabs(
            selected_index=0,
            on_change=self._on_tab_change,
            indicator_color=COLORS["accent"],
            label_color=COLORS["text"],
            unselected_label_color=COLORS["subtext"],
            tabs=[
                ft.Tab(text="Whitelist"),
                ft.Tab(text="Operators"),
                ft.Tab(text="Banned Players"),
            ],
        )

        add_btn = ft.ElevatedButton(
            "Add",
            bgcolor=COLORS["accent"],
            color=COLORS["text"],
            on_click=self._add_player,
        )

        if self.selected:
            self._refresh_list()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Player Management", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    server_dd,
                ], spacing=16),
                ft.Container(height=8),
                tabs,
                ft.Container(height=12),
                ft.Row([self.input_field, add_btn, self.status_text], spacing=12),
                ft.Container(height=8),
                ft.Divider(color=COLORS["border"]),
                self.player_list,
            ], expand=True),
            padding=32,
            expand=True,
        )

    def _refresh_list(self):
        if not self.selected:
            return
        self.player_list.controls.clear()
        if self.active_tab == "whitelist":
            players = self.sm.get_whitelist(self.selected)
            action = lambda name: self.sm.remove_whitelist(self.selected, name)
            action_label = "Remove"
        elif self.active_tab == "ops":
            players = self.sm.get_ops(self.selected)
            action = lambda name: self.sm.remove_op(self.selected, name)
            action_label = "Remove"
        else:
            players = self.sm.get_banned_players(self.selected)
            action = lambda name: self.sm.unban_player(self.selected, name)
            action_label = "Unban"

        if not players:
            self.player_list.controls.append(
                ft.Text("No players here yet", color=COLORS["subtext"], size=13)
            )
        else:
            for p in players:
                name = p.get("name", "Unknown")
                self.player_list.controls.append(self._player_row(name, action_label, action))
        try:
            self.player_list.update()
        except Exception:
            pass

    def _player_row(self, name: str, action_label: str, action_fn):
        def do_action(e, n=name):
            action_fn(n)
            self._refresh_list()

        return ft.Container(
            content=ft.Row([
                ft.Text("👤", size=16),
                ft.Text(name, color=COLORS["text"], size=13, expand=True),
                ft.ElevatedButton(
                    action_label,
                    bgcolor=COLORS["danger"],
                    color=COLORS["text"],
                    on_click=do_action,
                ),
            ], spacing=12),
            bgcolor=COLORS["card"],
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border=ft.border.all(1, COLORS["border"]),
        )

    def _add_player(self, e):
        name = self.input_field.value.strip()
        if not name or not self.selected:
            return
        if self.active_tab == "whitelist":
            self.sm.add_whitelist(self.selected, name)
        elif self.active_tab == "ops":
            self.sm.add_op(self.selected, name)
        else:
            self.sm.ban_player(self.selected, name)
        self.input_field.value = ""
        self.status_text.value = f"✅ Added {name}"
        self.status_text.color = COLORS["accent2"]
        try:
            self.input_field.update()
            self.status_text.update()
        except Exception:
            pass
        self._refresh_list()

    def _on_tab_change(self, e):
        tabs = ["whitelist", "ops", "banned"]
        self.active_tab = tabs[e.control.selected_index]
        self._refresh_list()

    def _on_server_change(self, e):
        self.selected = e.control.value
        self._refresh_list()
