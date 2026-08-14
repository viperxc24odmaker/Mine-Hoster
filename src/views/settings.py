import threading
import flet as ft
from src.server_manager import ServerManager
from src.version_fetcher import clear_cache
from src.java_runtime import download_java, installed_jres
from src.theme import COLORS


class SettingsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.selected = app.selected_server or (
            self.sm.get_servers()[0].name if self.sm.get_servers() else None
        )
        self.props_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)
        self.prop_fields = {}
        self.jre_status = ft.Text("", color=COLORS["subtext"], size=12)
        self.jre_progress = ft.ProgressBar(
            value=0,
            visible=False,
            color=COLORS["accent"],
            bgcolor=COLORS["surface2"],
        )

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
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Save Properties",
                            bgcolor=COLORS["accent2"],
                            color=COLORS["text"],
                            on_click=self._save_props,
                        ),
                        self.status_text,
                    ],
                    spacing=12,
                ),
            ]
        else:
            server_inner = [
                ft.Text("No servers found.", color=COLORS["subtext"], size=13)
            ]

        server_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Server Properties",
                        size=16,
                        weight=ft.FontWeight.W_600,
                        color=COLORS["text"],
                    ),
                    ft.Text(
                        "Edit server.properties for the selected server",
                        color=COLORS["subtext"],
                        size=13,
                    ),
                    ft.Container(height=8),
                ]
                + server_inner
            ),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )

        jre_buttons = [
            ft.ElevatedButton(
                f"Download JRE {version}",
                bgcolor=COLORS["surface2"],
                color=COLORS["text"],
                on_click=lambda e, v=version: self._download_jre(v),
            )
            for version in (17, 21, 25)
        ]

        jre_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Java / JRE Download Manager",
                        size=16,
                        weight=ft.FontWeight.W_600,
                        color=COLORS["text"],
                    ),
                    ft.Text(
                        "Download private Eclipse Temurin JREs without installing Java system-wide. MineHoster will use these automatically when a server needs them.",
                        color=COLORS["subtext"],
                        size=12,
                    ),
                    ft.Container(height=8),
                    ft.Row(jre_buttons, spacing=8),
                    self.jre_progress,
                    self.jre_status,
                    self._installed_jres_text(),
                ]
            ),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )

        app_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Application",
                        size=16,
                        weight=ft.FontWeight.W_600,
                        color=COLORS["text"],
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Refresh Version Cache",
                                bgcolor=COLORS["surface2"],
                                color=COLORS["text"],
                                on_click=self._clear_cache,
                            ),
                            ft.Text(
                                "Clears cached version lists so they re-fetch from Mojang/PaperMC/Fabric",
                                color=COLORS["subtext"],
                                size=12,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Delete Selected Server",
                                bgcolor=COLORS["danger"],
                                color=COLORS["text"],
                                on_click=self._delete_server,
                            ),
                            ft.Text(
                                "Permanently deletes the server and all its files",
                                color=COLORS["danger"],
                                size=12,
                            ),
                        ],
                        spacing=12,
                    ),
                ]
            ),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )

        if self.selected:
            self._load_props()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Settings",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS["text"],
                    ),
                    ft.Text(
                        "Configure your servers, Java runtimes and application",
                        color=COLORS["subtext"],
                        size=13,
                    ),
                    ft.Container(height=16),
                    server_section,
                    ft.Container(height=16),
                    jre_section,
                    ft.Container(height=16),
                    app_section,
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=32,
            expand=True,
        )

    def _installed_jres_text(self):
        installed = installed_jres()
        text = (
            ", ".join(f"Java {version}" for version, _, _ in installed)
            if installed
            else "No private JREs downloaded yet."
        )
        return ft.Text(
            f"Installed private runtimes: {text}",
            color=COLORS["muted"],
            size=11,
        )

    def _download_jre(self, version):
        self.jre_progress.visible = True
        self.jre_progress.value = 0
        self.jre_status.color = COLORS["subtext"]
        self.jre_status.value = f"Preparing JRE {version}..."
        self._safe_update()

        def worker():
            def progress(stage, message, percent=None):
                self.jre_status.value = message
                self.jre_status.color = COLORS["subtext"]
                if percent is not None:
                    self.jre_progress.value = percent / 100
                self._safe_update()

            try:
                download_java(version, progress)
                self.jre_progress.value = 1
                self.jre_status.color = COLORS["accent2"]
                self.jre_status.value = f"✓ JRE {version} installed successfully."
            except Exception as exc:
                self.jre_status.color = COLORS["danger"]
                self.jre_status.value = f"✕ JRE {version} download failed: {exc}"
            finally:
                self.jre_progress.visible = False
                self._safe_update()

        threading.Thread(target=worker, daemon=True).start()

    def _load_props(self):
        if not self.selected:
            return
        props = self.sm.get_properties(self.selected)
        self.props_col.controls.clear()
        self.prop_fields.clear()
        priority_keys = [
            "server-port",
            "online-mode",
            "enable-command-block",
            "max-players",
            "difficulty",
            "gamemode",
            "pvp",
            "white-list",
            "motd",
            "view-distance",
            "spawn-protection",
            "allow-flight",
            "allow-nether",
        ]
        ordered_keys = [k for k in priority_keys if k in props] + [
            k for k in props if k not in priority_keys
        ]
        for key in ordered_keys:
            field = ft.TextField(
                label=key,
                value=props[key],
                border_color=COLORS["border"],
                focused_border_color=COLORS["accent"],
                label_style=ft.TextStyle(color=COLORS["subtext"]),
                color=COLORS["text"],
                bgcolor=COLORS["surface2"],
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
        self.sm.update_properties(
            self.selected,
            {key: field.value for key, field in self.prop_fields.items()},
        )
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

    def _safe_update(self):
        try:
            self.jre_progress.update()
            self.jre_status.update()
        except Exception:
            pass
