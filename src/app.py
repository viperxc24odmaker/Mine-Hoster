import flet as ft
from src.views.dashboard import DashboardView
from src.views.create_server import CreateServerView
from src.views.console import ConsoleView
from src.views.files import FileManagerView
from src.views.plugins import PluginsView
from src.views.players import PlayersView
from src.views.settings import SettingsView
from src.theme import COLORS


class MineHosterApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = "dashboard"
        self.selected_server = None
        self.nav_refs = {}

    def initialize(self):
        p = self.page
        p.title = "MineHoster"
        p.bgcolor = COLORS["bg"]
        p.padding = 0
        p.spacing = 0
        p.window_width = 1200
        p.window_height = 750
        p.window_min_width = 900
        p.window_min_height = 600
        p.fonts = {
            "Inter": "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2"
        }
        p.theme = ft.Theme(font_family="Inter")
        self._build_layout()
        p.update()

    def _build_layout(self):
        sidebar = self._build_sidebar()
        self._main_content = ft.Container(
            content=DashboardView(self).build(),
            expand=True,
            bgcolor=COLORS["bg"],
        )
        self.page.add(
            ft.Row(
                [sidebar, self._main_content],
                spacing=0,
                expand=True,
            )
        )

    def _build_sidebar(self):
        logo = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text("M", color=COLORS["accent"], size=22, weight=ft.FontWeight.BOLD),
                    bgcolor=COLORS["accent"] + "22",
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                ),
                ft.Text("MineHoster", color=COLORS["text"], size=16, weight=ft.FontWeight.BOLD),
            ], spacing=10),
            padding=ft.padding.symmetric(horizontal=20, vertical=24),
        )

        nav_items = [
            ("dashboard", "🏠", "Dashboard"),
            ("create", "➕", "New Server"),
            ("console", "💻", "Console"),
            ("files", "📁", "File Manager"),
            ("plugins", "🔧", "Plugins & Mods"),
            ("players", "👥", "Players"),
            ("settings", "⚙️", "Settings"),
        ]

        nav_buttons = []
        for key, icon, label in nav_items:
            btn = self._nav_button(key, icon, label)
            self.nav_refs[key] = btn
            nav_buttons.append(btn)

        return ft.Container(
            content=ft.Column([
                logo,
                ft.Divider(color=COLORS["border"], height=1),
                ft.Container(
                    content=ft.Column(nav_buttons, spacing=4),
                    padding=ft.padding.symmetric(horizontal=12, vertical=12),
                ),
            ], spacing=0),
            bgcolor=COLORS["surface"],
            width=220,
            border=ft.border.only(right=ft.BorderSide(1, COLORS["border"])),
        )

    def _nav_button(self, key, icon, label):
        is_active = key == self.current_view

        def on_click(e, k=key):
            self.navigate(k)

        container = ft.Container(
            content=ft.Row([
                ft.Text(icon, size=16),
                ft.Text(label, color=COLORS["text"] if is_active else COLORS["subtext"], size=13),
            ], spacing=10),
            bgcolor=COLORS["accent"] + "22" if is_active else ft.colors.TRANSPARENT,
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_click=on_click,
            ink=True,
        )
        return container

    def navigate(self, view_key: str):
        self.current_view = view_key
        views = {
            "dashboard": DashboardView,
            "create": CreateServerView,
            "console": ConsoleView,
            "files": FileManagerView,
            "plugins": PluginsView,
            "players": PlayersView,
            "settings": SettingsView,
        }
        view_class = views.get(view_key, DashboardView)
        self._main_content.content = view_class(self).build()

        # Update nav highlight
        for k, container in self.nav_refs.items():
            is_active = k == view_key
            row = container.content
            row.controls[1].color = COLORS["text"] if is_active else COLORS["subtext"]
            container.bgcolor = COLORS["accent"] + "22" if is_active else ft.colors.TRANSPARENT

        self.page.update()
