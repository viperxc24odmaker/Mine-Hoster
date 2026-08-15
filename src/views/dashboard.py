import threading
import flet as ft
from src.server_manager import ServerManager
from src.server_icons import get_icon
from src.theme import COLORS


class DashboardView:
    """Compact hosting-panel dashboard inspired by modern Minecraft panels."""

    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()

    def build(self):
        servers = self.sm.get_servers()
        total = len(servers)
        running = sum(self.sm.is_running(s.name) for s in servers)
        starting = sum(s.name in self.app.starting_servers for s in servers)
        stopped = max(0, total - running - starting)
        return ft.Container(content=ft.Column([
            self._header(total, running, starting), self._stats(total, running, starting, stopped), ft.Container(height=20),
            ft.Row([ft.Column([ft.Text("Servers", color=COLORS["text"], size=19, weight=ft.FontWeight.BOLD), ft.Text("Manage your Minecraft instances from one place.", color=COLORS["subtext"], size=11)], spacing=2, expand=True), ft.ElevatedButton("+  New server", bgcolor=COLORS["accent"], color=COLORS["text"], style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9), padding=ft.padding.symmetric(horizontal=16, vertical=12)), on_click=lambda e: self.app.navigate("create"))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=10), ft.Column([self._server_card(s) for s in servers] or [self._empty_state()], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True, spacing=0), padding=ft.padding.symmetric(horizontal=28, vertical=24), expand=True, bgcolor=COLORS["bg"])

    def _header(self, total, running, starting):
        state = "All systems operational" if not starting else f"{starting} server{'s' if starting != 1 else ''} starting"
        state_color = COLORS["accent2"] if not starting else COLORS["warning"]
        return ft.Container(content=ft.Row([ft.Column([ft.Text("Dashboard", color=COLORS["text"], size=28, weight=ft.FontWeight.BOLD), ft.Text(f"{running} online  •  {total} total", color=COLORS["subtext"], size=12)], spacing=3), ft.Container(content=ft.Row([ft.Container(width=7, height=7, bgcolor=state_color, border_radius=10), ft.Text(state, color=COLORS["text"], size=10, weight=ft.FontWeight.W_500)], spacing=8), bgcolor=COLORS["surface2"], border=ft.border.all(1, COLORS["border"]), border_radius=18, padding=ft.padding.symmetric(horizontal=12, vertical=8))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), padding=ft.padding.only(bottom=18))

    def _stats(self, total, running, starting, stopped):
        return ft.Row([self._stat_card("SERVERS", total, "Managed", COLORS["accent"]), self._stat_card("ONLINE", running, "Ready to join", COLORS["accent2"]), self._stat_card("STARTING", starting, "Booting now", COLORS["warning"]), self._stat_card("OFFLINE", stopped, "Stopped", COLORS["muted"])], spacing=10)

    def _stat_card(self, title, value, subtitle, accent):
        return ft.Container(content=ft.Row([ft.Container(width=3, height=42, bgcolor=accent, border_radius=3), ft.Column([ft.Text(title, color=COLORS["muted"], size=8, weight=ft.FontWeight.BOLD), ft.Text(str(value), color=COLORS["text"], size=23, weight=ft.FontWeight.BOLD), ft.Text(subtitle, color=COLORS["subtext"], size=9)], spacing=1)], spacing=11), bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=11, padding=13, expand=True)

    def _server_card(self, server):
        running = self.sm.is_running(server.name); starting = server.name in self.app.starting_servers
        accent = COLORS["warning"] if starting else (COLORS["accent2"] if running else COLORS["muted"]); status = "STARTING" if starting else ("ONLINE" if running else "OFFLINE")
        def refresh_dashboard():
            try: self.app._main_content.content = DashboardView(self.app).build(); self.app.page.update()
            except Exception: pass
        def finish_start(ok): self.app.starting_servers.discard(server.name); refresh_dashboard()
        def start_worker():
            try: ok = self.sm.start_server(server.name)
            except Exception as exc: self.sm._emit(server.name, f"[ERROR] Startup failed: {exc}"); ok = False
            finish_start(ok)
        def toggle(e):
            if server.name in self.app.starting_servers: return
            self.app.selected_server = server.name
            if running: self.sm.stop_server(server.name); refresh_dashboard()
            else: self.app.starting_servers.add(server.name); refresh_dashboard(); threading.Thread(target=start_worker, daemon=True).start()
        def console(e): self.app.selected_server = server.name; self.app.navigate("console")
        def settings(e): self.app.selected_server = server.name; self.app.navigate("settings")
        def delete(e):
            if server.name in self.app.starting_servers: return
            def cancel(ev): dialog.open = False; self.app.page.update()
            def confirm(ev):
                dialog.open = False; self.app.page.update(); self.app.starting_servers.discard(server.name)
                try: self.sm.delete_server(server.name)
                except Exception as exc: self.sm._emit(server.name, f"[ERROR] Delete failed: {exc}")
                if self.app.selected_server == server.name: self.app.selected_server = None
                self.app.navigate("dashboard")
            dialog = ft.AlertDialog(modal=True, title=ft.Text(f"Delete {server.name}?"), content=ft.Text("This permanently deletes the server folder, world and configuration. This cannot be undone."), actions=[ft.TextButton("Cancel", on_click=cancel), ft.ElevatedButton("Delete Server", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=confirm)])
            self.app.page.dialog = dialog; dialog.open = True; self.app.page.update()
        meta = f"{server.loader.title()}  •  {server.version}  •  {server.ram_mb} MB RAM  •  Port {server.port}"
        action_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.padding.symmetric(horizontal=11, vertical=9))
        icon = get_icon(server.name)
        return ft.Container(content=ft.Column([
            ft.Row([ft.Container(content=ft.Text(icon, size=22), width=48, height=48, alignment=ft.alignment.center, bgcolor=COLORS["accent_soft"], border_radius=12), ft.Column([ft.Row([ft.Text(server.name, color=COLORS["text"], size=14, weight=ft.FontWeight.BOLD), ft.Container(content=ft.Text(status, color=accent, size=8, weight=ft.FontWeight.BOLD), bgcolor=accent + "22", border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=4))], spacing=8), ft.Text(meta, color=COLORS["subtext"], size=9)], spacing=4, expand=True), ft.Text("●" if running else ("◌" if starting else "○"), color=accent, size=12)], spacing=12),
            ft.Divider(height=1, color=COLORS["border"]),
            ft.Row([ft.Text("Local server instance", color=COLORS["muted"], size=9, expand=True), ft.TextButton("Console", style=action_style, on_click=console), ft.TextButton("Settings", style=action_style, on_click=settings), ft.TextButton("Delete", style=action_style, on_click=delete, disabled=starting), ft.ElevatedButton("Starting…" if starting else ("Stop" if running else "Start"), bgcolor=COLORS["danger"] if running else COLORS["accent2"], color=COLORS["text"], disabled=starting, style=action_style, on_click=toggle)], spacing=6),
            ft.ProgressBar(visible=starting, value=None, color=COLORS["warning"], bgcolor=COLORS["surface2"])
        ], spacing=9), bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=12, padding=15)

    def _empty_state(self):
        return ft.Container(content=ft.Column([ft.Container(content=ft.Text("+", color=COLORS["accent"], size=28, weight=ft.FontWeight.BOLD), width=52, height=52, alignment=ft.alignment.center, bgcolor=COLORS["accent_soft"], border_radius=14), ft.Text("No servers yet", color=COLORS["text"], size=17, weight=ft.FontWeight.BOLD), ft.Text("Create your first Minecraft server and MineHoster will handle the setup.", color=COLORS["subtext"], size=10), ft.ElevatedButton("Create server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create"))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=9), alignment=ft.alignment.center, padding=55, bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=12)
