import sys
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
    return _original_start_server(self, name)


_server_manager.ServerManager.start_server = _start_server_with_auto_setup


class MineHosterApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = 'dashboard'
        self.selected_server = None
        self.nav_refs = {}
        self._main_content = None
        self.starting_servers = set()

    def initialize(self):
        page = self.page
        page.title = 'MineHoster'
        page.bgcolor = COLORS['bg']
        page.padding = 0
        page.spacing = 0
        page.window_width = 1240
        page.window_height = 780
        page.window_min_width = 980
        page.window_min_height = 640
        try:
            root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
            icon = root / 'assets' / 'minehoster_build_icon.ico'
            if icon.exists():
                page.window.icon = str(icon)
        except Exception:
            pass
        page.theme = ft.Theme(font_family='Inter')
        page.fonts = {'Inter': 'https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2'}
        self._build_layout()
        page.update()

    def _build_layout(self):
        self._main_content = ft.Container(content=DashboardView(self).build(), expand=True, bgcolor=COLORS['bg'])
        self.page.add(ft.Row([self._build_sidebar(), self._main_content], spacing=0, expand=True))

    def _build_sidebar(self):
        logo = ft.Container(
            content=ft.Row([
                ft.Container(content=ft.Text('M', color=COLORS['accent'], size=20, weight=ft.FontWeight.BOLD), bgcolor=COLORS['accent_soft'], border_radius=10, padding=ft.padding.symmetric(horizontal=10, vertical=7)),
                ft.Column([ft.Text('MineHoster', color=COLORS['text'], size=16, weight=ft.FontWeight.BOLD), ft.Text('Minecraft control panel', color=COLORS['muted'], size=9)], spacing=1),
            ], spacing=10),
            padding=ft.padding.only(left=18, right=18, top=20, bottom=18),
        )
        items = [
            ('dashboard', '⌂', 'Dashboard'),
            ('bedrock', '◇', 'Bedrock'),
            ('create', '+', 'New Server'),
            ('console', '>', 'Console'),
            ('files', '□', 'File Manager'),
            ('plugins', '◇', 'Plugins & Mods'),
            ('players', '○', 'Players'),
            ('settings', '⚙', 'Settings'),
            ('hosting', '◈', 'Hosting Settings'),
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
                ft.Container(content=ft.Column(buttons, spacing=4), padding=ft.padding.symmetric(horizontal=10, vertical=14)),
                ft.Container(expand=True),
                ft.Container(content=ft.Column([ft.Text('MineHoster', color=COLORS['muted'], size=10), ft.Text('Local server manager', color=COLORS['subtext'], size=11)], spacing=2), padding=ft.padding.only(left=18, bottom=18)),
            ], spacing=0, expand=True),
            bgcolor=COLORS['surface'], width=232, border=ft.border.only(right=ft.BorderSide(1, COLORS['border'])),
        )

    def _nav_button(self, key, icon, label):
        active = key == self.current_view
        return ft.Container(
            content=ft.Row([ft.Text(icon, color=COLORS['accent'] if active else COLORS['muted'], size=16, weight=ft.FontWeight.BOLD), ft.Text(label, color=COLORS['text'] if active else COLORS['subtext'], size=12)], spacing=12),
            bgcolor=COLORS['accent_soft'] if active else None,
            border_radius=9,
            padding=ft.padding.symmetric(horizontal=12, vertical=11),
            on_click=lambda e, selected=key: self.navigate(selected),
            ink=True,
        )

    def navigate(self, view_key):
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
        }
        view_cls = views.get(view_key, DashboardView)
        try:
            new_content = view_cls(self).build()
        except Exception as exc:
            new_content = ft.Container(
                content=ft.Column([
                    ft.Text('Could not load this section', size=22, weight=ft.FontWeight.BOLD, color=COLORS['text']),
                    ft.Text(str(exc), color=COLORS['danger'], selectable=True),
                    ft.ElevatedButton('Back to Dashboard', bgcolor=COLORS['accent'], color=COLORS['text'], on_click=lambda e: self.navigate('dashboard')),
                ], spacing=12),
                padding=32, expand=True,
            )
        self.current_view = view_key
        self._main_content.content = new_content
        for key, container in self.nav_refs.items():
            active = key == view_key
            row = container.content
            row.controls[0].color = COLORS['accent'] if active else COLORS['muted']
            row.controls[1].color = COLORS['text'] if active else COLORS['subtext']
            container.bgcolor = COLORS['accent_soft'] if active else None
        try:
            self.page.update()
        except Exception:
            pass
