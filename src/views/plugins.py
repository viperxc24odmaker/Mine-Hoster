import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS


class PluginsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.plugin_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(
                content=ft.Text("No servers found.", color=COLORS["subtext"]),
                padding=32,
            )

        cfg = self.sm.servers.get(self.selected)
        type_label = "Mods" if cfg and cfg.loader in ("fabric", "forge") else "Plugins"

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

        file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.app.page.overlay.append(file_picker)
        self.app.page.update()

        if self.selected:
            self._refresh_plugins()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"{type_label} Manager", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    server_dd,
                ], spacing=16),
                ft.Container(height=4),
                ft.Text(
                    f"Add .jar files to your server's {type_label.lower()} folder",
                    color=COLORS["subtext"], size=13,
                ),
                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton(
                        f"+ Add {type_label[:-1]} (.jar)",
                        bgcolor=COLORS["accent"],
                        color=COLORS["text"],
                        on_click=lambda e: file_picker.pick_files(
                            allow_multiple=False,
                            allowed_extensions=["jar"],
                        ),
                    ),
                    ft.ElevatedButton(
                        "Refresh",
                        bgcolor=COLORS["surface2"],
                        color=COLORS["text"],
                        on_click=lambda e: self._refresh_plugins(),
                    ),
                ], spacing=12),
                self.status_text,
                ft.Container(height=8),
                ft.Divider(color=COLORS["border"]),
                self.plugin_list,
            ], scroll=ft.ScrollMode.AUTO),
            padding=32,
            expand=True,
        )

    def _refresh_plugins(self):
        if not self.selected:
            return
        plugins = self.sm.list_plugins(self.selected)
        cfg = self.sm.servers.get(self.selected)
        type_label = "Mod" if cfg and cfg.loader in ("fabric", "forge") else "Plugin"
        self.plugin_list.controls.clear()

        if not plugins:
            self.plugin_list.controls.append(
                ft.Text(f"No {type_label.lower()}s installed yet", color=COLORS["subtext"], size=13)
            )
        else:
            for p in plugins:
                self.plugin_list.controls.append(self._plugin_row(p, type_label))
        try:
            self.plugin_list.update()
        except Exception:
            pass

    def _plugin_row(self, name: str, type_label: str):
        def remove(e, n=name):
            self.sm.remove_plugin(self.selected, n)
            self.status_text.value = f"✅ Removed {n}"
            self.status_text.color = COLORS["accent2"]
            try:
                self.status_text.update()
            except Exception:
                pass
            self._refresh_plugins()

        return ft.Container(
            content=ft.Row([
                ft.Text("🧩", size=16),
                ft.Text(name, color=COLORS["text"], size=13, expand=True),
                ft.ElevatedButton(
                    "Remove",
                    bgcolor=COLORS["danger"],
                    color=COLORS["text"],
                    on_click=remove,
                ),
            ], spacing=12),
            bgcolor=COLORS["card"],
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border=ft.border.all(1, COLORS["border"]),
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if e.files and self.selected:
            path = e.files[0].path
            self.sm.add_plugin(self.selected, path)
            self.status_text.value = f"✅ Added {e.files[0].name}"
            self.status_text.color = COLORS["accent2"]
            try:
                self.status_text.update()
            except Exception:
                pass
            self._refresh_plugins()

    def _on_server_change(self, e):
        self.selected = e.control.value
        self._refresh_plugins()
