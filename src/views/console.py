import flet as ft
import threading
from src.playit import PlayitManager
from src.server_manager import ServerManager
from src.theme import COLORS


class ConsoleView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.playit = PlayitManager.get()
        servers = self.sm.get_servers()
        self.selected = app.selected_server or (servers[0].name if servers else None)
        self.log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
        self.cmd_field = ft.TextField(
            hint_text="Command, e.g. list or say hello", border_color=COLORS["border"],
            focused_border_color=COLORS["accent"], color=COLORS["text"], bgcolor=COLORS["surface2"],
            expand=True, on_submit=self._send_cmd,
        )
        self.status_text = ft.Text("No server selected", color=COLORS["subtext"], size=10)
        self.tunnel_text = ft.Text("Tunnel: inactive", color=COLORS["subtext"], size=10)
        self.playit_running = False
        self.start_btn = None

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(
                content=ft.Column(
                    [ft.Text("Console", color=COLORS["text"], size=24, weight=ft.FontWeight.BOLD), ft.Text("Create a server first, then its live process console appears here.", color=COLORS["subtext"], size=12)],
                    spacing=5,
                ), padding=30,
            )
        names = {server.name for server in servers}
        if self.selected not in names:
            self.selected = servers[0].name
        self.app.selected_server = self.selected
        running = self.sm.is_running(self.selected)
        self.start_btn = ft.ElevatedButton(
            "Stop server" if running else "Start server", bgcolor=COLORS["danger"] if running else COLORS["accent2"],
            color=COLORS["text"], on_click=self._toggle_server,
        )
        server_dd = ft.Dropdown(
            value=self.selected, options=[ft.dropdown.Option(server.name) for server in servers], on_change=self._on_server_change,
            border_color=COLORS["border"], focused_border_color=COLORS["accent"], color=COLORS["text"], bgcolor=COLORS["surface2"], width=210,
        )
        self.sm.unregister_console_callbacks(self.selected)
        self.sm.register_console_callback(self.selected, self._on_log)
        self.status_text.value = "Running" if running else "Stopped"
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column([ft.Text("Live Console", color=COLORS["text"], size=22, weight=ft.FontWeight.BOLD), self.status_text], spacing=3),
                            server_dd, self.start_btn,
                            ft.ElevatedButton("Restart", bgcolor=COLORS["warning"], color="#111111", on_click=self._restart),
                        ], spacing=10,
                    ),
                    ft.Row(
                        [ft.ElevatedButton("Enable playit.gg", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._toggle_playit), self.tunnel_text], spacing=12,
                    ),
                    ft.Container(
                        content=self.log_list, bgcolor="#0A0D12", border=ft.border.all(1, COLORS["border"]), border_radius=12, padding=12, expand=True,
                    ),
                    ft.Row(
                        [self.cmd_field, ft.ElevatedButton("Send", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=self._send_cmd)], spacing=8,
                    ),
                ], expand=True, spacing=8,
            ), padding=30, expand=True,
        )

    def _on_log(self, line):
        lower = line.lower()
        color = COLORS["danger"] if "error" in lower or "exception" in lower else COLORS["warning"] if "warn" in lower else COLORS["accent2"] if "done" in lower or "started" in lower else COLORS["text"]
        self.log_list.controls.append(ft.Text(line, color=color, size=11, font_family="Courier New", selectable=True))
        if len(self.log_list.controls) > 2000:
            del self.log_list.controls[:500]
        self.status_text.value = "Running" if self.selected and self.sm.is_running(self.selected) else "Stopped"
        try:
            self.log_list.update()
            self.status_text.update()
        except Exception:
            pass

    def _send_cmd(self, e):
        command = (self.cmd_field.value or "").strip()
        if not command or not self.selected:
            return
        if self.sm.send_command(self.selected, command):
            self._on_log(f"> {command.lstrip('/')}")
            self.cmd_field.value = ""
        else:
            self._on_log("[ERROR] Command was not sent because the server is not running.")
        try:
            self.cmd_field.update()
        except Exception:
            pass

    def _toggle_server(self, e):
        if not self.selected:
            return
        if self.sm.is_running(self.selected):
            self.sm.stop_server(self.selected)
        elif not self.sm.start_server(self.selected):
            self._on_log("[ERROR] Start failed. See the console error above.")
        self._refresh_start_button()

    def _refresh_start_button(self):
        if not self.start_btn:
            return
        running = self.sm.is_running(self.selected)
        self.start_btn.text = "Stop server" if running else "Start server"
        self.start_btn.bgcolor = COLORS["danger"] if running else COLORS["accent2"]
        try:
            self.start_btn.update()
        except Exception:
            pass

    def _restart(self, e):
        if self.selected:
            threading.Thread(target=self._restart_worker, daemon=True).start()

    def _restart_worker(self):
        ok = self.sm.restart_server(self.selected)
        self._on_log("[MineHoster] Restart complete." if ok else "[ERROR] Restart failed.")
        self._refresh_start_button()

    def _on_server_change(self, e):
        self.selected = e.control.value
        self.app.selected_server = self.selected
        self.log_list.controls.clear()
        self.sm.unregister_console_callbacks(self.selected)
        self.sm.register_console_callback(self.selected, self._on_log)
        self._refresh_start_button()
        try:
            self.log_list.update()
        except Exception:
            pass

    def _toggle_playit(self, e):
        if self.playit_running:
            self.playit.stop()
            self.playit_running = False
            self.tunnel_text.value = "Tunnel: inactive"
        else:
            if not self.playit.is_installed():
                self._on_log("[playit.gg] Installing agent...")
                def install_and_start():
                    ok = self.playit.install(lambda stage, message: self._on_log(f"[playit.gg] {message}"))
                    if ok:
                        self._start_playit()
                        self.playit_running = True
                threading.Thread(target=install_and_start, daemon=True).start()
            else:
                self._start_playit()
                self.playit_running = True
            self.tunnel_text.value = "Tunnel: starting..."
        try:
            e.control.text = "Disable playit.gg" if self.playit_running else "Enable playit.gg"
            e.control.update()
            self.tunnel_text.update()
        except Exception:
            pass

    def _start_playit(self):
        cfg = self.sm.servers.get(self.selected)
        if not cfg:
            return
        self.playit.start(port=cfg.port, bedrock=cfg.loader == "bedrock")
        self.playit.register_callback(lambda line: self._on_log(f"[playit.gg] {line}"))
