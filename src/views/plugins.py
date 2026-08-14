from __future__ import annotations

import threading
from pathlib import Path

import flet as ft

from src.modrinth import ModrinthClient, ModrinthError, installed_plugin_names
from src.server_manager import ServerManager
from src.theme import COLORS


class PluginsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        servers = self.sm.get_servers()
        self.selected = app.selected_server or (servers[0].name if servers else None)
        self.client = ModrinthClient()
        self.plugin_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.market_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)
        self.search_field = ft.TextField(label="Search Modrinth", hint_text="Essentials, ViaVersion, LuckPerms...", expand=True, on_submit=self._search)
        self.version_field = ft.TextField(label="Minecraft version", hint_text="1.21.8", width=150)
        self.loader_field = ft.Dropdown(
            label="Loader",
            width=150,
            options=[ft.dropdown.Option(v) for v in ["Auto", "paper", "purpur", "spigot", "bukkit", "fabric", "forge", "neoforge"]],
            value="Auto",
        )
        self.progress = ft.ProgressBar(value=0, visible=False, expand=True)

    def _cfg(self):
        return self.sm.servers.get(self.selected) if self.selected else None

    def _project_type(self):
        cfg = self._cfg()
        return "mod" if cfg and cfg.loader in ("fabric", "forge", "neoforge") else "plugin"

    def _loader(self):
        value = self.loader_field.value or "Auto"
        if value != "Auto":
            return value
        cfg = self._cfg()
        if cfg and cfg.loader in ("paper", "purpur", "spigot", "bukkit", "fabric", "forge", "neoforge"):
            return cfg.loader
        return ""

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(content=ft.Text("No servers found.", color=COLORS["subtext"]), padding=32)

        cfg = self._cfg()
        kind = "Mods" if self._project_type() == "mod" else "Plugins"
        server_dd = ft.Dropdown(
            label="Server",
            value=self.selected,
            options=[ft.dropdown.Option(s.name) for s in servers],
            on_change=self._on_server_change,
            border_color=COLORS["border"],
            focused_border_color=COLORS["accent"],
            color=COLORS["text"],
            bgcolor=COLORS["surface2"],
            width=220,
        )
        if cfg:
            self.version_field.value = cfg.version

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(f"{kind} Marketplace", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                        ft.Text("Browse and install compatible projects from Modrinth.", color=COLORS["subtext"], size=13),
                    ], expand=True),
                    server_dd,
                ]),
                ft.Container(height=4),
                ft.Container(
                    content=ft.Row([
                        self.search_field,
                        self.version_field,
                        self.loader_field,
                        ft.ElevatedButton("Search", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=self._search),
                    ], spacing=10),
                    bgcolor=COLORS["card"],
                    border_radius=12,
                    padding=14,
                    border=ft.border.all(1, COLORS["border"]),
                ),
                ft.Row([self.progress, self.status_text], spacing=12),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Modrinth Marketplace", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                            self.market_list,
                        ], expand=True),
                        bgcolor=COLORS["card"], border_radius=12, padding=16, expand=True,
                        border=ft.border.all(1, COLORS["border"]),
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text("Installed", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                                ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: self._refresh_plugins()),
                            ]),
                            self.plugin_list,
                        ], expand=True),
                        bgcolor=COLORS["card"], border_radius=12, padding=16, expand=True,
                        border=ft.border.all(1, COLORS["border"]),
                    ),
                ], expand=True, spacing=14),
            ], expand=True, scroll=ft.ScrollMode.AUTO),
            padding=24, expand=True,
        )

    def _search(self, e=None):
        query = (self.search_field.value or "").strip()
        version = (self.version_field.value or "").strip()
        loader = self._loader()
        self.status_text.value = "Searching Modrinth..."
        self.status_text.color = COLORS["subtext"]
        self.progress.visible = True
        self.progress.value = None
        self._safe_update()

        def worker():
            try:
                results = self.client.search(query, version, loader, 30)
                self.market_list.controls.clear()
                if not results:
                    self.market_list.controls.append(ft.Text("No compatible projects found.", color=COLORS["subtext"]))
                else:
                    for project in results:
                        self.market_list.controls.append(self._project_card(project, version, loader))
                self.status_text.value = f"Found {len(results)} project(s)."
                self.status_text.color = COLORS["accent2"]
            except Exception as exc:
                self.market_list.controls.clear()
                self.market_list.controls.append(ft.Text(f"Marketplace error: {exc}", color=COLORS["danger"], size=12))
                self.status_text.value = "Modrinth search failed."
                self.status_text.color = COLORS["danger"]
            finally:
                self.progress.visible = False
                self._safe_update()

        threading.Thread(target=worker, daemon=True).start()

    def _project_card(self, project, minecraft_version, loader):
        project_id = project.get("project_id") or project.get("slug")
        title = project.get("title") or project_id or "Unknown project"
        description = (project.get("description") or "No description available.").strip()
        downloads = project.get("downloads", 0)
        follows = project.get("follows", 0)

        def install(e, pid=project_id, name=title):
            self._install_project(pid, name, minecraft_version, loader)

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Text(description[:180] + ("…" if len(description) > 180 else ""), size=12, color=COLORS["subtext"]),
                    ft.Text(f"↓ {downloads:,} downloads  •  ♥ {follows:,} follows", size=11, color=COLORS["subtext"]),
                ], expand=True, spacing=4),
                ft.ElevatedButton("Install", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=install),
            ], spacing=14),
            bgcolor=COLORS["surface2"], border_radius=10, padding=14,
            border=ft.border.all(1, COLORS["border"]),
        )

    def _install_project(self, project_id, name, minecraft_version, loader):
        if not self.selected:
            return
        self.status_text.value = f"Preparing {name}..."
        self.status_text.color = COLORS["subtext"]
        self.progress.visible = True
        self.progress.value = 0
        self._safe_update()

        def worker():
            try:
                version = self.client.choose_version(project_id, minecraft_version, loader)
                if not version:
                    raise ModrinthError(f"No compatible release of {name} was found for Minecraft {minecraft_version}.")
                directory = self.sm.get_plugins_dir(self.selected)
                if not directory:
                    raise ModrinthError("The selected server does not support plugins or mods.")
                existing = installed_plugin_names(directory)
                primary = next((f for f in version.get("files", []) if f.get("primary")), None)
                filename = Path(primary.get("filename", "")).name if primary else ""
                if filename.lower() in existing:
                    self.status_text.value = f"{name} is already installed."
                    self.status_text.color = COLORS["accent2"]
                else:
                    def progress(done, total, file_name):
                        self.progress.value = (done / total) if total else None
                        self.status_text.value = f"Downloading {file_name}"
                        self._safe_update()
                    files = self.client.install_version(version, directory, progress)
                    self.status_text.value = f"Installed {name} ({len(files)} file(s))."
                    self.status_text.color = COLORS["accent2"]
                    self._refresh_plugins()
            except Exception as exc:
                self.status_text.value = f"Install failed: {exc}"
                self.status_text.color = COLORS["danger"]
            finally:
                self.progress.visible = False
                self._safe_update()

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_plugins(self):
        if not self.selected:
            return
        names = self.sm.list_plugins(self.selected)
        self.plugin_list.controls.clear()
        kind = "mod" if self._project_type() == "mod" else "plugin"
        if not names:
            self.plugin_list.controls.append(ft.Text(f"No {kind}s installed yet.", color=COLORS["subtext"], size=13))
        else:
            for name in names:
                self.plugin_list.controls.append(self._installed_row(name, kind))
        self._safe_update()

    def _installed_row(self, name, kind):
        def remove(e, n=name):
            self.sm.remove_plugin(self.selected, n)
            self.status_text.value = f"Removed {n}"
            self.status_text.color = COLORS["accent2"]
            self._refresh_plugins()
        return ft.Container(
            content=ft.Row([
                ft.Text("🧩" if kind == "plugin" else "🧱", size=16),
                ft.Text(name, color=COLORS["text"], size=12, expand=True),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Remove", on_click=remove),
            ]),
            bgcolor=COLORS["surface2"], border_radius=8, padding=10,
        )

    def _on_server_change(self, e):
        self.selected = e.control.value
        cfg = self._cfg()
        if cfg:
            self.version_field.value = cfg.version
        self.market_list.controls.clear()
        self._refresh_plugins()
        self._safe_update()

    def _safe_update(self):
        try:
            self.app.page.update()
        except Exception:
            pass
