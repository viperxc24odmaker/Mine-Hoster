import sys
import threading
import time
from pathlib import Path
import flet as ft
from src import server_manager as _server_manager
from src.java_runtime import ensure_java
from src.version_fetcher import get_versions_for_loader
from src.theme import COLORS
from src.views.console import ConsoleView
from src.views.create_server import CreateServerView
from src.views.dashboard import DashboardView
from src.views.bedrock import BedrockView
from src.views.files import FileManagerView
from src.views.players import PlayersView
from src.views.plugins import PluginsView
from src.views.settings import SettingsView
from src.views.hosting_settings import HostingSettingsView
from src.views.playit import PlayitView

_server_manager._find_java = ensure_java
_original_start_server = _server_manager.ServerManager.start_server


def _ensure_server_assets(manager, cfg):
    folder = Path(cfg.folder)
    folder.mkdir(parents=True, exist_ok=True)
    if cfg.loader == 'bedrock' and not (folder / 'bedrock_server.exe').exists():
        urls = get_versions_for_loader('bedrock')
        url = urls.get(cfg.version) or next(iter(urls.values()), None)
        if not url:
            raise RuntimeError('No Bedrock server download is available for this version.')
        manager._create_bedrock(cfg, folder, url, lambda kind, message, percent=None: manager._emit(cfg.name, f'[Download] {message}'))
    elif cfg.loader == 'forge':
        script = folder / ('run.bat' if _server_manager.os.name == 'nt' else 'run.sh')
        if not script.exists():
            urls = get_versions_for_loader('forge')
            url = urls.get(cfg.version)
            if not url:
                raise RuntimeError(f'No Forge installer is available for Minecraft {cfg.version}.')
            manager._prepare_forge(cfg, folder, url, lambda kind, message, percent=None: manager._emit(cfg.name, f'[Download] {message}'))
    elif cfg.loader != 'bedrock':
        jar = folder / 'server.jar'
        if not jar.exists() or jar.stat().st_size < 1024:
            urls = get_versions_for_loader(cfg.loader)
            url = urls.get(cfg.version)
            if not url:
                raise RuntimeError(f'No {cfg.loader} server download is available for Minecraft {cfg.version}.')
            part = folder / 'server.jar.part'
            try:
                manager._download(url, part, lambda kind, message, percent=None: manager._emit(cfg.name, f'[Download] {message}'))
                part.replace(jar)
            finally:
                part.unlink(missing_ok=True)
    if cfg.loader != 'bedrock' and not (folder / 'eula.txt').exists():
        (folder / 'eula.txt').write_text('eula=true\n', encoding='utf-8')
    if cfg.loader != 'bedrock' and not (folder / 'server.properties').exists():
        manager._write_properties(folder, cfg)


def _start_server_with_auto_setup(self, name):
    cfg = self.servers.get(name)
    if not cfg or self.is_running(name):
        return bool(cfg and self.is_running(name))
    try:
        _ensure_server_assets(self, cfg)
    except Exception as exc:
        self._emit(name, f'[ERROR] Server setup failed: {exc}')
        return False
    for attempt in range(2):
        started = _original_start_server(self, name)
        if not started:
            return False
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if self.is_running(name):
                stable_until = time.monotonic() + 1.5
                while time.monotonic() < stable_until:
                    if not self.is_running(name):
                        break
                    time.sleep(0.1)
                if self.is_running(name):
                    return True
                break
            time.sleep(0.1)
        if attempt == 0:
            self._emit(name, '[MineHoster] Server exited during first startup; retrying once automatically...')
            time.sleep(0.5)
    return self.is_running(name)


_server_manager.ServerManager.start_server = _start_server_with_auto_setup


class MineHosterApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = 'dashboard'
        self.selected_server = None
        self.nav_refs = {}
        self._main_content = None
        self.starting_servers = set()
        self._navigation_token = 0
        self._navigation_lock = threading.Lock()

    def initialize(self):
        page = self.page
        page.title = 'MineHoster'
        page.bgcolor = COLORS['bg']
        page.padding = 0
        page.spacing = 0
        page.window_width = 1320
        page.window_height = 820
        page.window_min_width = 1000
        page.window_min_height = 660
        try:
            root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
            icon = root / 'assets' / 'minehoster_build_icon.ico'
            if icon.exists():
                page.window.icon = str(icon)
        except Exception:
            pass
        page.theme = ft.Theme(font_family='Inter', visual_density=ft.VisualDensity.COMFORTABLE)
        page.fonts = {'Inter': 'https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2'}
        self._build_layout()
        page.update()

    def _build_layout(self):
        self._main_content = ft.Container(content=DashboardView(self).build(), expand=True, bgcolor=COLORS['bg'])
        self.page.add(ft.Row([self._build_sidebar(), self._main_content], spacing=0, expand=True))

    def _build_sidebar(self):
        logo = ft.Container(
            content=ft.Row([
                ft.Container(content=ft.Text('M', color=COLORS['text'], size=19, weight=ft.FontWeight.BOLD), bgcolor=COLORS['accent_soft'], border=ft.border.all(1, COLORS['border']), border_radius=11, padding=ft.padding.symmetric(horizontal=11, vertical=8)),
                ft.Column([ft.Text('MineHoster', color=COLORS['text'], size=17, weight=ft.FontWeight.BOLD), ft.Text('LOCAL SERVER CONTROL', color=COLORS['muted'], size=8, weight=ft.FontWeight.BOLD)], spacing=1),
            ], spacing=10),
            padding=ft.padding.only(left=18, right=18, top=20, bottom=18),
        )
        items = [
            ('dashboard', '⌂', 'Overview'),
            ('create', '+', 'New Server'),
            ('console', '>', 'Console'),
            ('players', '○', 'Players'),
            ('plugins', '◇', 'Plugins & Mods'),
            ('playit', '↗', 'Playit.gg'),
            ('files', '□', 'File Manager'),
            ('bedrock', '◇', 'Bedrock'),
            ('settings', '⚙', 'Server Settings'),
            ('hosting', '◈', 'MineHoster Settings'),
        ]
        buttons = []
        for key, icon, label in items:
            button = self._nav_button(key, icon, label)
            self.nav_refs[key] = button
            buttons.append(button)
        return ft.Container(
            content=ft.Column([
                logo,
                ft.Container(height=1, bgcolor=COLORS['border']),
                ft.Container(content=ft.Column(buttons, spacing=3), padding=ft.padding.symmetric(horizontal=9, vertical=13)),
                ft.Container(expand=True),
                ft.Container(content=ft.Column([ft.Text('MINEHOSTER', color=COLORS['muted'], size=9, weight=ft.FontWeight.BOLD), ft.Text('Graphite • Local-first • No cloud required', color=COLORS['subtext'], size=10)], spacing=2), padding=ft.padding.only(left=18, bottom=18)),
            ], spacing=0, expand=True),
            bgcolor=COLORS['surface'], width=238, border=ft.border.only(right=ft.BorderSide(1, COLORS['border'])),
        )

    def _nav_button(self, key, icon, label):
        active = key == self.current_view
        return ft.TextButton(
            content=ft.Row([
                ft.Text(icon, color=COLORS['text'] if active else COLORS['muted'], size=16, weight=ft.FontWeight.BOLD),
                ft.Text(label, color=COLORS['text'] if active else COLORS['subtext'], size=12, weight=ft.FontWeight.W_500),
            ], spacing=12),
            style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=12, vertical=11), alignment=ft.alignment.center_left, shape=ft.RoundedRectangleBorder(radius=9), bgcolor=COLORS['accent_soft'] if active else None),
            on_click=lambda e, selected=key: self.navigate(selected),
        )

    def _set_nav_state(self, view_key):
        self.current_view = view_key
        for key, button in self.nav_refs.items():
            active = key == view_key
            row = button.content
            row.controls[0].color = COLORS['text'] if active else COLORS['muted']
            row.controls[1].color = COLORS['text'] if active else COLORS['subtext']
            button.style.bgcolor = COLORS['accent_soft'] if active else None

    def navigate(self, view_key):
        if self._main_content is None:
            return
        views = {
            'dashboard': DashboardView,
            'bedrock': BedrockView,
            'create': CreateServerView,
            'console': ConsoleView,
            'files': FileManagerView,
            'plugins': PluginsView,
            'players': PlayersView,
            'settings': SettingsView,
            'hosting': HostingSettingsView,
            'playit': PlayitView,
        }
        view_cls = views.get(view_key, DashboardView)
        self._set_nav_state(view_key)
        self._main_content.content = ft.Container(content=ft.Column([ft.ProgressRing(color=COLORS['accent']), ft.Text('Loading section…', color=COLORS['subtext'], size=12)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=12), expand=True)
        try:
            self.page.update()
        except Exception:
            pass
        try:
            new_content = view_cls(self).build()
        except Exception as exc:
            new_content = ft.Container(content=ft.Column([ft.Text('Could not load this section', size=22, weight=ft.FontWeight.BOLD, color=COLORS['text']), ft.Text(str(exc), color=COLORS['danger'], selectable=True), ft.ElevatedButton('Back to Overview', bgcolor=COLORS['accent'], color=COLORS['bg'], on_click=lambda e: self.navigate('dashboard'))], spacing=12), padding=32, expand=True)
        self._main_content.content = new_content
        try:
            self.page.update()
        except Exception:
            pass


def main(page: ft.Page):
    app = MineHosterApp(page)
    app.initialize()
