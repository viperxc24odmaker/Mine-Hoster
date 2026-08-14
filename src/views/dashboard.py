import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS


class DashboardView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()

    def build(self):
        servers = self.sm.get_servers()
        total = len(servers)
        running = sum(1 for server in servers if self.sm.is_running(server.name))
        stopped = total - running
        return ft.Container(
            content=ft.Column(
                [
                    self._header(total, running),
                    ft.Row(
                        [
                            self._stat_card("Servers", total, "Total managed", COLORS["accent"]),
                            self._stat_card("Online", running, "Currently running", COLORS["accent2"]),
                            self._stat_card("Offline", stopped, "Stopped safely", COLORS["danger"]),
                        ], spacing=12,
                    ),
                    ft.Container(height=24),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Your servers", color=COLORS["text"], size=17, weight=ft.FontWeight.BOLD),
                                    ft.Text("Start, stop and jump into your server tools.", color=COLORS["subtext"], size=11),
                                ], spacing=3,
                            ),
                            ft.ElevatedButton("+  New server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create")),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=10),
                    ft.Column([self._server_card(server) for server in servers] or [self._empty_state()], spacing=10, scroll=ft.ScrollMode.AUTO),
                ], expand=True, spacing=0,
            ),
            padding=30, expand=True,
        )

    def _header(self, total, running):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [ft.Text("Dashboard", color=COLORS["text"], size=25, weight=ft.FontWeight.BOLD), ft.Text(f"{running} running · {total} total", color=COLORS["subtext"], size=12)],
                        spacing=4,
                    ),
                    ft.Container(
                        content=ft.Row([ft.Container(width=7, height=7, bgcolor=COLORS["accent2"], border_radius=10), ft.Text("Local control", color=COLORS["subtext"], size=11)], spacing=7),
                        bgcolor=COLORS["surface2"], border=ft.border.all(1, COLORS["border"]), border_radius=20,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.only(bottom=22),
        )

    def _stat_card(self, title, value, subtitle, accent):
        return ft.Container(
            content=ft.Column([ft.Text(title.upper(), color=COLORS["muted"], size=10, weight=ft.FontWeight.BOLD), ft.Text(str(value), color=accent, size=29, weight=ft.FontWeight.BOLD), ft.Text(subtitle, color=COLORS["subtext"], size=10)], spacing=5),
            bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=12, padding=17, expand=True,
        )

    def _server_card(self, server):
        running = self.sm.is_running(server.name)
        accent = COLORS["accent2"] if running else COLORS["muted"]
        status = "RUNNING" if running else "STOPPED"

        def toggle(e):
            ok = self.sm.stop_server(server.name) if running else self.sm.start_server(server.name)
            if not ok and not running:
                self.app.selected_server = server.name
                self.app.navigate("console")
            else:
                self.app.navigate("dashboard")

        def console(e):
            self.app.selected_server = server.name
            self.app.navigate("console")

        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(server.name, color=COLORS["text"], size=14, weight=ft.FontWeight.BOLD),
                                    ft.Container(content=ft.Text(status, color=accent, size=9, weight=ft.FontWeight.BOLD), bgcolor=accent + "22", border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=4)),
                                ], spacing=9,
                            ),
                            ft.Text(f"{server.loader.title()}  •  {server.version}  •  {server.port}  •  {server.ram_mb} MB RAM", color=COLORS["subtext"], size=10),
                        ], spacing=7, expand=True,
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton("Console", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=console),
                            ft.ElevatedButton("Stop" if running else "Start", bgcolor=COLORS["danger"] if running else COLORS["accent2"], color=COLORS["text"], on_click=toggle),
                        ], spacing=7,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=12, padding=16,
        )

    def _empty_state(self):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("✦", color=COLORS["accent"], size=35),
                    ft.Text("Nothing here yet", color=COLORS["text"], size=16, weight=ft.FontWeight.BOLD),
                    ft.Text("Create a server and MineHoster will manage the rest.", color=COLORS["subtext"], size=11),
                    ft.ElevatedButton("Create your first server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create")),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
            ),
            alignment=ft.alignment.center, padding=60, bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=12,
        )
