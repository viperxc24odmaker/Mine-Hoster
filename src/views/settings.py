import flet as ft
from src.server_manager import ServerManager
from src.version_fetcher import clear_cache
from src.theme import COLORS


class SettingsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.props_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)
        self.prop_fields: dict[str, ft.TextField] = {}

    def build(self):
        servers = self.sm.get_servers()

        if servers:
            server_inner = [
                ft.Dropdown(
                    value=self.selected,
                    options=[ft.dropdown.Option(s.name) for s in servers],
                    on_change=self._on_server_change,
                    border_color=COLORS["border"],
                    focused_border_color=COLORS["accent"],
                    color=COLORS["text"],
                    bgcolor=COLORS["surface2"],
                    width=220,
                ),
                ft.Container(height=8),
                self.props_col,
                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton(
                        "Save Properties",
                        bgcolor=COLORS["accent2"],
                        color=COLORS["text"],
                        on_click=self._save_props,
                    ),
                    self.status_text,
                ], spacing=12),
            ]
        else:
            server_inner = [ft.Text("No servers found.", color=COLORS["subtext"], size=13)]

        server_section = ft.Container(
            content=ft.Column([
                ft.Text("Server Properties", size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]),
                ft.Text("Edit server.properties for the selected server", color=COLORS["subtext"], size=13),
                ft.Container(height=8),
            ] + server_inner),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )

        app_section = ft.Container(
            content=ft.Column([
                ft.Text("Application", size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]),
                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton(
                        "Refresh Version Cache",
                        bgcolor=COLORS["surface2"],
                        color=COLORS["text"],
                        on_click=self._clear_cache,
                    ),
                    ft.Text("Clears cached version lists so they re-fetch from Mojang/PaperMC/Fabric", color=COLORS["subtext"], size=12),
                ], spacing=12),
                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton(
                        "Delete Selected Server",
                        bgcolor=COLORS["danger"],
                        color=COLORS["text"],
                        on_click=self._delete_server,
                    ),
                    ft.Text("Permanently deletes the server and all its files", color=COLORS["danger"], size=12),
                ], spacing=12),
            ]),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )

        if self.selected:
            self._load_props()

        return ft.Container(
            content=ft.Column([
                ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                ft.Text("Configure your servers and application", color=COLORS["subtext"], size=13),
                ft.Container(height=16),
                server_section,
                ft.Container(height=16),
                app_section,
            ], scroll=ft.ScrollMode.AUTO),
            padding=32,
            expand=True,
        )

    def _load_props(self):
        if not self.selected:
            return
        props = self.sm.get_properties(self.selected)
        self.props_col.controls.clear()
        self.prop_fields.clear()

        # Show important properties first, then the rest
        priority_keys = [
            "server-port", "online-mode", "enable-command-block", "max-players",
            "difficulty", "gamemode", "pvp", "white-list", "motd",
            "view-distance", "spawn-protection", "allow-flight", "allow-nether",
        ]
        ordered_keys = [k for k in priority_keys if k in props]
        ordered_keys += [k for k in props if k not in priority_keys]

        for key in ordered_keys:
            val = props[key]
            field = ft.TextField(
                label=key, value=val,
                border_color=COLORS["border"], focused_border_color=COLORS["accent"],
                label_style=ft.TextStyle(color=COLORS["subtext"]),
                color=COLORS["text"], bgcolor=COLORS["surface2"],
            )
            self.prop_fields[key] = field
            self.props_col.controls.append(field)
        try:
            self.props_col.update()
        except Exception:
            pass

    def _save_props(self, e):
        if not self.selected:
            return
        updates = {k: f.value for k, f in self.prop_fields.items()}
        self.sm.update_properties(self.selected, updates)
        self.status_text.value = "✅ Saved!"
        self.status_text.color = COLORS["accent2"]
        try:
            self.status_text.update()
        except Exception:
            pass

    def _on_server_change(self, e):
        self.selected = e.control.value
        self._load_props()

    def _clear_cache(self, e):
        clear_cache()
        e.control.text = "✅ Cache Cleared"
        try:
            e.control.update()
        except Exception:
            pass

    def _delete_server(self, e):
        if self.selected:
            self.sm.delete_server(self.selected)
            self.selected = None
            self.app.selected_server = None
            self.app.navigate("dashboard")
