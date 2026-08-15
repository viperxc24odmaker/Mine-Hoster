import os
import subprocess
import threading
from pathlib import Path
import flet as ft
from src.app import MineHosterApp
from src import server_manager as _server_manager
from src.java_runtime import ensure_java as _real_ensure_java
from src.theme import COLORS
from src.views.playit_tunnel import PlayitTunnelView
from src.views.settings_v2 import SettingsViewV2
from src.views.hosting_settings_v2 import HostingSettingsViewV2
from src.views.players_v2 import PlayersViewV2
from src.runtime_scheduler import start_scheduler


def _cached_ensure_java(required, progress_cb=None):
    runtime_dir = Path.home() / ".minehoster" / "runtimes"
    exe = "java.exe" if os.name == "nt" else "java"
    for root in runtime_dir.glob("temurin-*"):
        java = root / "bin" / exe
        if not java.is_file(): continue
        try:
            result = subprocess.run([str(java), "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
            output = result.stdout or ""; marker = 'version "'
            if marker in output:
                raw = output.split(marker, 1)[1].split('"', 1)[0]; detected = int(raw.split(".")[1]) if raw.startswith("1.") else int(raw.split(".")[0])
                if detected == required:
                    if progress_cb: progress_cb("done", f"JRE {required} found in MineHoster cache. Reusing it.", 100)
                    return str(java)
        except (OSError, subprocess.SubprocessError, ValueError, IndexError): pass
    return _real_ensure_java(required, progress_cb)


_server_manager.ensure_java = _cached_ensure_java
_server_manager._find_java = _cached_ensure_java


def _build_sidebar(self):
    logo = ft.Container(content=ft.Row([ft.Container(content=ft.Text("M", size=19, weight=ft.FontWeight.BOLD, color=COLORS["text"]), bgcolor=COLORS["accent"], border_radius=11, padding=ft.padding.symmetric(horizontal=10, vertical=7)), ft.Column([ft.Text("MineHoster", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("LOCAL • MINECRAFT HOSTING", size=8, color=COLORS["muted"])], spacing=1)], spacing=10), padding=ft.padding.only(left=18, right=18, top=20, bottom=18))
    items = [("dashboard", "⌂", "Overview"), ("bedrock", "◇", "Bedrock"), ("create", "+", "Create Server"), ("console", ">_", "Console"), ("files", "□", "Files"), ("plugins", "◆", "Plugins & Mods"), ("players", "●", "Players"), ("playit", "↗", "Playit.gg"), ("settings", "⚙", "Settings"), ("hosting", "◈", "Hosting")]
    buttons = []
    for key, icon, label in items:
        b = self._nav_button(key, icon, label); self.nav_refs[key] = b; buttons.append(b)
    return ft.Container(content=ft.Column([logo, ft.Container(height=1, bgcolor=COLORS["border"]), ft.Container(content=ft.Column(buttons, spacing=3), padding=ft.padding.symmetric(horizontal=10, vertical=14)), ft.Container(expand=True), ft.Container(content=ft.Column([ft.Text("MINEHOSTER", size=9, color=COLORS["muted"]), ft.Text("Local-first • no cloud required", size=10, color=COLORS["subtext"])], spacing=2), padding=ft.padding.only(left=18, bottom=18))], spacing=0, expand=True), bgcolor=COLORS["surface"], width=238, border=ft.border.only(right=ft.BorderSide(1, COLORS["border"])))


def _navigate(self, view_key):
    views = {
        "dashboard": __import__("src.views.dashboard", fromlist=["DashboardView"]).DashboardView,
        "bedrock": __import__("src.views.bedrock", fromlist=["BedrockView"]).BedrockView,
        "create": __import__("src.views.create_server", fromlist=["CreateServerView"]).CreateServerView,
        "console": __import__("src.views.console", fromlist=["ConsoleView"]).ConsoleView,
        "files": __import__("src.views.files", fromlist=["FileManagerView"]).FileManagerView,
        "plugins": __import__("src.views.plugins", fromlist=["PluginsView"]).PluginsView,
        "players": PlayersViewV2,
        "playit": PlayitTunnelView,
        "settings": SettingsViewV2,
        "hosting": HostingSettingsViewV2,
    }
    if self._main_content is None: return
    self._set_nav_state(view_key)
    try: self._main_content.content = views.get(view_key, views["dashboard"])(self).build(); self.page.update()
    except Exception as exc:
        self._main_content.content = ft.Container(content=ft.Column([ft.Text("Section failed to load", size=22, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text(str(exc), color=COLORS["danger"], selectable=True), ft.Button("Back to Overview", on_click=lambda e: self.navigate("dashboard"))], spacing=12), padding=30, expand=True); self.page.update()


MineHosterApp._build_sidebar = _build_sidebar
MineHosterApp.navigate = _navigate


def main(page: ft.Page):
    app = MineHosterApp(page)
    app.initialize()
    try: start_scheduler()
    except Exception: pass


ft.app(target=main)
