import threading
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
        running = sum(self.sm.is_running(s.name) for s in servers)
        starting = sum(s.name in self.app.starting_servers for s in servers)
        stopped = max(0, total - running - starting)
        return ft.Container(
            content=ft.Column([
                self._header(total, running, starting),
                ft.Row([
                    self._stat_card("Servers", total, "Total managed", COLORS["accent"]),
                    self._stat_card("Online", running, "Ready to join", COLORS["accent2"]),
                    self._stat_card("Starting", starting, "Booting now", COLORS["accent"]),
                    self._stat_card("Offline", stopped, "Stopped safely", COLORS["muted"]),
                ], spacing=10),
                ft.Container(height=24),
                ft.Row([
                    ft.Column([
                        ft.Text("Your servers", color=COLORS["text"], size=18, weight=ft.FontWeight.BOLD),
                        ft.Text("A clean command center for every Minecraft server.", color=COLORS["subtext"], size=11),
                    ], spacing=3),
                    ft.ElevatedButton("+  New server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create")),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=10),
                ft.Column([self._server_card(s) for s in servers] or [self._empty_state()], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
            ], expand=True, spacing=0),
            padding=30,
            expand=True,
        )

    def _header(self, total, running, starting):
        text = f"{running} online" + (f" · {starting} starting" if starting else "") + f" · {total} total"
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("Dashboard", color=COLORS["text"], size=27, weight=ft.FontWeight.BOLD),
                    ft.Text(text, color=COLORS["subtext"], size=12),
                ], spacing=4),
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=7, height=7, bgcolor=COLORS["accent2"], border_radius=10),
                        ft.Text("MineHoster is ready", color=COLORS["subtext"], size=11),
                    ], spacing=7),
                    bgcolor=COLORS["surface2"],
                    border=ft.border.all(1, COLORS["border"]),
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.only(bottom=22),
        )

    def _stat_card(self, title, value, subtitle, accent):
        return ft.Container(
            content=ft.Column([
                ft.Text(title.upper(), color=COLORS["muted"], size=9, weight=ft.FontWeight.BOLD),
                ft.Text(str(value), color=accent, size=27, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, color=COLORS["subtext"], size=10),
            ], spacing=4),
            bgcolor=COLORS["card"],
            border=ft.border.all(1, COLORS["border"]),
            border_radius=14,
            padding=16,
            expand=True,
        )

    def _server_card(self, server):
        running = self.sm.is_running(server.name)
        starting = server.name in self.app.starting_servers
        accent = COLORS["accent"] if starting else (COLORS["accent2"] if running else COLORS["muted"])
        status = "STARTING" if starting else ("ONLINE" if running else "OFFLINE")

        def refresh_dashboard():
            try:
                self.app._main_content.content = DashboardView(self.app).build()
                self.app.page.update()
            except Exception:
                pass

        def finish_start(ok):
            self.app.starting_servers.discard(server.name)
            if ok:
                # Keep the real process state as the source of truth.
                refresh_dashboard()
            else:
                refresh_dashboard()

        def start_worker():
            try:
                ok = self.sm.start_server(server.name)
            except Exception as exc:
                self.sm._emit(server.name, f"[ERROR] Startup failed: {exc}")
                ok = False
            finish_start(ok)

        def toggle(e):
            if server.name in self.app.starting_servers:
                return
            self.app.selected_server = server.name
            if running:
                self.sm.stop_server(server.name)
                refresh_dashboard()
            else:
                # Set the state and rebuild immediately, before JRE/server setup starts.
                self.app.starting_servers.add(server.name)
                self.app.navigate("dashboard")
                threading.Thread(target=start_worker, daemon=True).start()

        def console(e):
            self.app.selected_server = server.name
            self.app.navigate("console")

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Row([
                        ft.Text(server.name, color=COLORS["text"], size=14, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Text(status, color=accent, size=9, weight=ft.FontWeight.BOLD),
                            bgcolor=accent + "22",
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        ),
                    ], spacing=9),
                    ft.Text(f"{server.loader.title()}  •  {server.version}  •  Port {server.port}  •  {server.ram_mb} MB RAM", color=COLORS["subtext"], size=10),
                    ft.ProgressBar(visible=starting, value=None, color=COLORS["accent"], bgcolor=COLORS["surface2"]),
                ], spacing=7, expand=True),
                ft.Row([
                    ft.ElevatedButton("Console", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=console),
                    ft.ElevatedButton(
                        "Starting…" if starting else ("Stop" if running else "Start"),
                        disabled=starting,
                        bgcolor=COLORS["danger"] if running else COLORS["accent2"],
                        color=COLORS["text"],
                        on_click=toggle,
                    ),
                ], spacing=7),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=COLORS["card"],
            border=ft.border.all(1, COLORS["border"]),
            border_radius=14,
            padding=17,
        )

    def _empty_state(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("✦", color=COLORS["accent"], size=35),
                ft.Text("Your server center is empty", color=COLORS["text"], size=17, weight=ft.FontWeight.BOLD),
                ft.Text("Create a server and MineHoster handles the setup.", color=COLORS["subtext"], size=11),
                ft.ElevatedButton("Create your first server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create")),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            alignment=ft.alignment.center,
            padding=60,
            bgcolor=COLORS["card"],
            border=ft.border.all(1, COLORS["border"]),
            border_radius=14,
        )
