import flet as ft
import threading
from src.server_manager import ServerManager
from src.playit import PlayitManager
from src.theme import COLORS


class ConsoleView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.playit = PlayitManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
        self.cmd_field = ft.TextField(
            hint_text="Enter command...",
            border_color=COLORS["border"],
            focused_border_color=COLORS["accent"],
            color=COLORS["text"],
            bgcolor=COLORS["surface2"],
            expand=True,
            on_submit=self._send_cmd,
        )
        self.tunnel_text = ft.Text("Tunnel: Not active", color=COLORS["subtext"], size=12)
        self.playit_running = False

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(
                content=ft.Text("No servers found. Create one first.", color=COLORS["subtext"]),
                padding=32,
            )

        server_dd = ft.Dropdown(
            value=self.selected,
            options=[ft.dropdown.Option(s.name) for s in servers],
            on_change=self._on_server_change,
            border_color=COLORS["border"],
            focused_border_color=COLORS["accent"],
            color=COLORS["text"],
            bgcolor=COLORS["surface2"],
            width=200,
        )

        is_running = self.sm.is_running(self.selected) if self.selected else False

        self.start_btn = ft.ElevatedButton(
            "Stop" if is_running else "Start",
            bgcolor=COLORS["danger"] if is_running else COLORS["accent2"],
            color=COLORS["text"],
            on_click=self._toggle_server,
        )
        self.restart_btn = ft.ElevatedButton(
            "Restart", bgcolor=COLORS["warning"], color="#000000",
            on_click=self._restart,
        )

        playit_btn = ft.ElevatedButton(
            "Enable Tunnel (playit.gg)",
            bgcolor=COLORS["accent"],
            color=COLORS["text"],
            on_click=self._toggle_playit,
        )

        # Register console callback
        if self.selected:
            self.sm.unregister_console_callbacks(self.selected)
            self.sm.register_console_callback(self.selected, self._on_log)
            self.playit.unregister_callbacks()
            self.playit.register_callback(self._on_playit_log)

        top_bar = ft.Row([
            ft.Text("Console", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            server_dd,
            self.start_btn,
            self.restart_btn,
        ], spacing=12)

        console_box = ft.Container(
            content=self.log_list,
            bgcolor=COLORS["surface2"],
            border_radius=10,
            border=ft.border.all(1, COLORS["border"]),
            padding=12,
            expand=True,
        )

        cmd_row = ft.Row([
            self.cmd_field,
            ft.ElevatedButton(
                "Send", bgcolor=COLORS["accent"], color=COLORS["text"],
                on_click=self._send_cmd,
            ),
        ], spacing=8)

        playit_row = ft.Row([
            playit_btn,
            self.tunnel_text,
        ], spacing=16)

        return ft.Container(
            content=ft.Column([
                top_bar,
                ft.Container(height=8),
                playit_row,
                ft.Container(height=8),
                console_box,
                ft.Container(height=8),
                cmd_row,
            ], expand=True),
            padding=32,
            expand=True,
        )

    def _on_log(self, line: str):
        color = COLORS["text"]
        if "[ERROR]" in line or "ERROR" in line:
            color = COLORS["danger"]
        elif "[WARN]" in line or "WARN" in line:
            color = COLORS["warning"]
        elif "Done" in line or "started" in line.lower():
            color = COLORS["accent2"]

        self.log_list.controls.append(
            ft.Text(line, color=color, size=12, font_family="Courier New", selectable=True)
        )
        try:
            self.log_list.update()
        except Exception:
            pass

    def _on_playit_log(self, line: str):
        self._on_log(f"[playit.gg] {line}")
        if self.playit.tunnel_address:
            self.tunnel_text.value = f"Tunnel: {self.playit.tunnel_address}"
            try:
                self.tunnel_text.update()
            except Exception:
                pass

    def _send_cmd(self, e):
        cmd = self.cmd_field.value.strip()
        if cmd and self.selected:
            self.sm.send_command(self.selected, cmd)
            self._on_log(f"> {cmd}")
            self.cmd_field.value = ""
            try:
                self.cmd_field.update()
            except Exception:
                pass

    def _toggle_server(self, e):
        if not self.selected:
            return
        if self.sm.is_running(self.selected):
            self.sm.stop_server(self.selected)
            self.start_btn.text = "Start"
            self.start_btn.bgcolor = COLORS["accent2"]
        else:
            self.sm.start_server(self.selected)
            self.start_btn.text = "Stop"
            self.start_btn.bgcolor = COLORS["danger"]
        try:
            self.start_btn.update()
        except Exception:
            pass

    def _restart(self, e):
        if self.selected:
            threading.Thread(target=self.sm.restart_server, args=(self.selected,), daemon=True).start()

    def _on_server_change(self, e):
        self.selected = e.control.value
        self.app.selected_server = self.selected
        if self.selected:
            self.sm.unregister_console_callbacks(self.selected)
            self.sm.register_console_callback(self.selected, self._on_log)
        self.log_list.controls.clear()
        try:
            self.log_list.update()
        except Exception:
            pass

    def _toggle_playit(self, e):
        if self.playit_running:
            self.playit.stop()
            self.playit_running = False
            self.tunnel_text.value = "Tunnel: Not active"
            e.control.text = "Enable Tunnel (playit.gg)"
            e.control.bgcolor = COLORS["accent"]
        else:
            if not self.playit.is_installed():
                self._on_log("[playit.gg] Downloading playit.gg agent...")
                def install_and_start():
                    ok = self.playit.install(lambda s, m: self._on_log(f"[playit.gg] {m}"))
                    if ok:
                        self._start_playit_for_server()
                        self.playit_running = True
                threading.Thread(target=install_and_start, daemon=True).start()
            else:
                self._start_playit_for_server()
                self.playit_running = True
            e.control.text = "Disable Tunnel"
            e.control.bgcolor = COLORS["danger"]
        try:
            e.control.update()
            self.tunnel_text.update()
        except Exception:
            pass

    def _start_playit_for_server(self):
        cfg = self.sm.servers.get(self.selected)
        is_bedrock = cfg and cfg.loader == "bedrock"
        port = cfg.port if cfg else 25565
        self.playit.start(port=port, bedrock=is_bedrock)

        # Register a disconnect callback so UI resets if tunnel dies on its own
        def on_disconnect(line: str):
            if "Disconnected" in line:
                self.playit_running = False
                self.tunnel_text.value = "Tunnel: Not active"
                try:
                    self.tunnel_text.update()
                except Exception:
                    pass
        self.playit.register_callback(on_disconnect)
