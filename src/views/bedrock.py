import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS

class BedrockView:
    def __init__(self, app): self.app = app; self.sm = ServerManager.get()
    def build(self):
        servers = [s for s in self.sm.get_servers() if s.loader == "bedrock"]
        running = sum(self.sm.is_running(s.name) for s in servers)
        return ft.Container(content=ft.Column([
            ft.Row([ft.Column([ft.Text("Bedrock", size=27, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Dedicated Bedrock server management", size=12, color=COLORS["subtext"])], spacing=3), ft.ElevatedButton("+  New Bedrock Server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create"))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=18), ft.Row([self._stat("Servers", len(servers), COLORS["accent"]), self._stat("Online", running, COLORS["accent2"]), self._stat("Offline", len(servers)-running, COLORS["muted"])], spacing=12),
            ft.Container(height=18), ft.Text("Your Bedrock servers", size=17, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Bedrock is managed separately from Java Edition.", size=11, color=COLORS["subtext"]), ft.Container(height=9),
            ft.Column([self._card(s) for s in servers] or [self._empty()], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True), padding=30, expand=True)
    def _stat(self, title, value, accent): return ft.Container(content=ft.Column([ft.Text(title.upper(), size=9, weight=ft.FontWeight.BOLD, color=COLORS["muted"]), ft.Text(str(value), size=27, weight=ft.FontWeight.BOLD, color=accent)], spacing=4), bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=12, padding=16, expand=True)
    def _card(self, s):
        running = self.sm.is_running(s.name); starting = self.sm.is_starting(s.name)
        status = "STARTING" if starting else ("ONLINE" if running else "OFFLINE"); accent = COLORS["accent"] if starting else (COLORS["accent2"] if running else COLORS["muted"])
        def toggle(e):
            if starting: return
            self.sm.stop_server(s.name) if running else self.sm.start_server(s.name); self.app.selected_server = s.name; self.app.navigate("bedrock")
        return ft.Container(content=ft.Row([ft.Column([ft.Row([ft.Text(s.name, size=14, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Container(content=ft.Text(status, size=9, weight=ft.FontWeight.BOLD, color=accent), bgcolor=accent+"22", border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=4))], spacing=9), ft.Text(f"Bedrock  •  {s.version}  •  Port {s.port}  •  {s.ram_mb} MB", size=10, color=COLORS["subtext"]), ft.ProgressBar(visible=starting, value=None, color=COLORS["accent"], bgcolor=COLORS["surface2"])], spacing=7, expand=True), ft.Row([ft.ElevatedButton("Console", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=lambda e: self._console(s.name)), ft.ElevatedButton("Starting…" if starting else ("Stop" if running else "Start"), disabled=starting, bgcolor=COLORS["danger"] if running else COLORS["accent2"], color=COLORS["text"], on_click=toggle)], spacing=7)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=14, padding=17)
    def _console(self, name): self.app.selected_server = name; self.app.navigate("console")
    def _empty(self): return ft.Container(content=ft.Column([ft.Text("Bedrock Edition", size=19, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("No Bedrock servers yet.", size=11, color=COLORS["subtext"]), ft.ElevatedButton("Create Bedrock Server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=lambda e: self.app.navigate("create"))], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=9), alignment=ft.alignment.center, padding=70, bgcolor=COLORS["card"], border=ft.border.all(1, COLORS["border"]), border_radius=14)
