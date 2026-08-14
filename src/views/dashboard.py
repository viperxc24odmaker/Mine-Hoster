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
        running = sum(1 for s in servers if self.sm.is_running(s.name))

        stat_cards = ft.Row([
            self._stat_card("Total Servers", str(total), "🖥️", COLORS["accent"]),
            self._stat_card("Running", str(running), "🟢", COLORS["accent2"]),
            self._stat_card("Stopped", str(total - running), "🔴", COLORS["danger"]),
        ], spacing=16)

        server_list = ft.Column(
            [self._server_card(s) for s in servers] if servers else [
                ft.Container(
                    content=ft.Column([
                        ft.Text("🎮", size=48),
                        ft.Text("No servers yet", color=COLORS["subtext"], size=16),
                        ft.Text("Create your first server to get started", color=COLORS["subtext"], size=13),
                        ft.ElevatedButton(
                            "Create Server",
                            bgcolor=COLORS["accent"],
                            color=COLORS["text"],
                            on_click=lambda e: self.app.navigate("create"),
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    alignment=ft.alignment.center,
                    padding=60,
                )
            ],
            spacing=12,
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Dashboard", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                        ft.Text("Manage your Minecraft servers", color=COLORS["subtext"], size=13),
                    ], spacing=4),
                    padding=ft.padding.only(bottom=24),
                ),
                stat_cards,
                ft.Container(height=24),
                ft.Row([
                    ft.Text("Your Servers", size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]),
                    ft.ElevatedButton(
                        "+ New Server",
                        bgcolor=COLORS["accent"],
                        color=COLORS["text"],
                        on_click=lambda e: self.app.navigate("create"),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=12),
                server_list,
            ], scroll=ft.ScrollMode.AUTO),
            padding=32,
            expand=True,
        )

    def _stat_card(self, label, value, icon, color):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Text(icon, size=20), ft.Text(label, color=COLORS["subtext"], size=12)], spacing=8),
                ft.Text(value, size=32, weight=ft.FontWeight.BOLD, color=color),
            ], spacing=8),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, color + "33"),
            expand=True,
        )

    def _server_card(self, server):
        is_running = self.sm.is_running(server.name)
        status_color = COLORS["accent2"] if is_running else COLORS["subtext"]
        status_text = "Running" if is_running else "Stopped"

        def start_stop(e):
            if is_running:
                self.sm.stop_server(server.name)
            else:
                self.sm.start_server(server.name)
            self.app.navigate("dashboard")

        def open_console(e):
            self.app.selected_server = server.name
            self.app.navigate("console")

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Row([
                        ft.Text(server.name, size=15, weight=ft.FontWeight.W_600, color=COLORS["text"]),
                        ft.Container(
                            content=ft.Text(status_text, size=11, color=status_color),
                            bgcolor=status_color + "22",
                            border_radius=20,
                            padding=ft.padding.symmetric(horizontal=10, vertical=3),
                        ),
                    ], spacing=10),
                    ft.Text(
                        f"{server.loader.capitalize()} {server.version} • Port {server.port} • {server.ram_mb}MB RAM",
                        color=COLORS["subtext"], size=12,
                    ),
                ], expand=True, spacing=6),
                ft.Row([
                    ft.IconButton(
                        icon=ft.icons.TERMINAL,
                        icon_color=COLORS["subtext"],
                        tooltip="Open Console",
                        on_click=open_console,
                    ),
                    ft.ElevatedButton(
                        "Stop" if is_running else "Start",
                        bgcolor=COLORS["danger"] if is_running else COLORS["accent2"],
                        color=COLORS["text"],
                        on_click=start_stop,
                    ),
                ], spacing=8),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=COLORS["card"],
            border_radius=12,
            padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )
