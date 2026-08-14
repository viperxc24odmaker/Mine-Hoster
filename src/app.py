import flet as ft
from src.theme import COLORS
from src.views.console import ConsoleView
from src.views.create_server import CreateServerView
from src.views.dashboard import DashboardView
from src.views.files import FileManagerView
from src.views.players import PlayersView
from src.views.plugins import PluginsView
from src.views.settings import SettingsView


class MineHosterApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = "dashboard"
        self.selected_server = None
        self.nav_refs = {}
        self._main_content = None

    def initialize(self):
        page = self.page
        page.title = "MineHoster"
        page.bgcolor = COLORS["bg"]
        page.padding = 0
        page.spacing = 0
        page.window_width = 1240
        page.window_height = 780
        page.window_min_width = 980
        page.window_min_height = 640
        page.theme = ft.Theme(font_family="Inter")
        page.fonts = {
            "Inter": "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2"
        }
        self._build_layout()
        page.update()

    def _build_layout(self):
        self._main_content = ft.Container(
            content=DashboardView(self).build(),
            expand=True,
            bgcolor=COLORS["bg"],
        )
        self.page.add(
            ft.Row([self._build_sidebar(), self._main_content], spacing=0, expand=True)
        )

    def _build_sidebar(self):
        logo = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Text("M", color=COLORS["accent"], size=20, weight=ft.FontWeight.BOLD),
                        bgcolor=COLORS["accent_soft"], border_radius=10,
                        padding=ft.padding.symmetric(horizontal=10, vertical=7),
                    ),
                    ft.Column(
                        [
                            ft.Text("MineHoster", color=COLORS["text"], size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Minecraft control panel", color=COLORS["muted"], size=9),
                        ], spacing=1,
                    ),
                ], spacing=10,
            ),
            padding=ft.padding.only(left=18, right=18, top=20, bottom=18),
        )
        items = [
            ("dashboard", "⌂", "Dashboard"), ("create", "+", "New Server"),
            ("console", ">", "Console"), ("files", "□", "File Manager"),
            ("plugins", "◇", "Plugins & Mods"), ("players", "○", "Players"),
            ("settings", "⚙", "Settings"),
        ]
        buttons = []
        for key, icon, label in items:
            button = self._nav_button(key, icon, label)
            self.nav_refs[key] = button
            buttons.append(button)
        return ft.Container(
            content=ft.Column(
                [
                    logo,
                    ft.Container(height=1, bgcolor=COLORS["border"]),
                    ft.Container(content=ft.Column(buttons, spacing=4), padding=ft.padding.symmetric(horizontal=10, vertical=14)),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Column(
                            [ft.Text("MineHoster", color=COLORS["muted"], size=10), ft.Text("Local server manager", color=COLORS["subtext"], size=11)],
                            spacing=2,
                        ),
                        padding=ft.padding.only(left=18, bottom=18),
                    ),
                ], spacing=0, expand=True,
            ),
            bgcolor=COLORS["surface"], width=232,
            border=ft.border.only(right=ft.BorderSide(1, COLORS["border"])),
        )

    def _nav_button(self, key, icon, label):
        active = key == self.current_view
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(icon, color=COLORS["accent"] if active else COLORS["muted"], size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(label, color=COLORS["text"] if active else COLORS["subtext"], size=12),
                ], spacing=12,
            ),
            bgcolor=COLORS["accent_soft"] if active else None,
            border_radius=9,
            padding=ft.padding.symmetric(horizontal=12, vertical=11),
            on_click=lambda e, selected=key: self.navigate(selected),
            ink=True,
        )

    def navigate(self, view_key: str):
        self.current_view = view_key
        views = {
            "dashboard": DashboardView, "create": CreateServerView, "console": ConsoleView,
            "files": FileManagerView, "plugins": PluginsView, "players": PlayersView, "settings": SettingsView,
        }
        self._main_content.content = views.get(view_key, DashboardView)(self).build()
        for key, container in self.nav_refs.items():
            active = key == view_key
            row = container.content
            row.controls[0].color = COLORS["accent"] if active else COLORS["muted"]
            row.controls[1].color = COLORS["text"] if active else COLORS["subtext"]
            container.bgcolor = COLORS["accent_soft"] if active else None
        self.page.update()
