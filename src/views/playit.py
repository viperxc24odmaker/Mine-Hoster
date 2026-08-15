from __future__ import annotations

import threading
import flet as ft
from src.playit import PlayitManager
from src.server_manager import ServerManager
from src.theme import COLORS


class PlayitView:
    """Dedicated Playit control center. It never opens a console window on Windows."""
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.playit = PlayitManager.get()
        servers = self.sm.get_servers()
        self.selected = app.selected_server or (servers[0].name if servers else None)
        self.status = ft.Text("Ready.", color=COLORS["subtext"], size=12)
        self.address = ft.Text(self.playit.tunnel_address or "No public address detected yet.", color=COLORS["accent2"], size=14, selectable=True)
        self.claim = ft.Text("", color=COLORS["warning"], size=12, selectable=True)
        self.log = ft.TextField(value="", multiline=True, read_only=True, min_lines=8, max_lines=14, expand=True, text_size=11)
        self.secret = ft.TextField(label="Optional Playit secret key", password=True, can_reveal_password=True, expand=True, hint_text="Use this for headless/account-connected startup")
        self.progress = ft.ProgressBar(value=0, visible=False, expand=True)
        self.playit.register_callback(self._on_log)

    def _cfg(self):
        return self.sm.servers.get(self.selected) if self.selected else None

    def build(self):
        servers = self.sm.get_servers()
        server_dd = ft.Dropdown(label="Server", value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._server_changed, width=240) if servers else ft.Text("Create a server first to bind a tunnel.", color=COLORS["subtext"])
        return ft.Container(content=ft.Column([
            ft.Row([ft.Column([ft.Text("Playit.gg", size=26, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Public Minecraft access without port forwarding.", color=COLORS["subtext"], size=13)], expand=True), server_dd]),
            ft.Container(height=4),
            ft.Row([
                self._card("Agent", "Install, connect and monitor the official Playit agent.", [
                    ft.Row([ft.ElevatedButton("Install / Update", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._install), ft.ElevatedButton("Connect", bgcolor=COLORS["accent2"], color=COLORS["bg"], on_click=self._connect), ft.ElevatedButton("Stop", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._stop)], wrap=True, spacing=8),
                    ft.Row([self.secret, ft.ElevatedButton("Connect with Secret", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._connect_secret)], spacing=8),
                    self.progress, self.status,
                ]),
                self._card("Tunnel", "Create or manage the Minecraft tunnel associated with the connected agent.", [
                    ft.Text("Public address", color=COLORS["subtext"], size=11), self.address,
                    ft.Row([ft.ElevatedButton("Create Free Minecraft Tunnel", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._create_tunnel), ft.TextButton("Open Playit Tunnel Manager", on_click=lambda e: self.playit.open_tunnel_setup())], wrap=True),
                    self.claim,
                    ft.Text("The first connection may require a one-time Playit claim. MineHoster opens the official Playit flow instead of storing account credentials.", color=COLORS["muted"], size=11),
                ]),
            ], spacing=14),
            self._card("Live Agent Output", "Useful when Playit reports a claim URL, tunnel address, or network error.", [self.log]),
        ], spacing=14, scroll=ft.ScrollMode.AUTO), padding=28, expand=True)

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text(subtitle, size=12, color=COLORS["subtext"]), ft.Container(height=6), *controls], spacing=8), bgcolor=COLORS["card"], border_radius=14, padding=18, border=ft.border.all(1, COLORS["border"]), expand=True)

    def _install(self, e):
        self.progress.visible = True; self.progress.value = 0; self.status.value = "Checking Playit agent..."; self._safe_update()
        def worker():
            ok = self.playit.install(self._progress)
            self.status.value = "✓ Playit agent is ready." if ok else "✕ Playit agent installation failed."
            self.status.color = COLORS["accent2"] if ok else COLORS["danger"]
            self.progress.visible = False; self._safe_update()
        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, stage, message, percent=0):
        self.status.value = message
        if percent is not None: self.progress.value = percent / 100
        self._safe_update()

    def _connect(self, e):
        self._start("")

    def _connect_secret(self, e):
        self._start(self.secret.value or "")

    def _start(self, secret):
        cfg = self._cfg()
        port = cfg.port if cfg else 25565
        bedrock = bool(cfg and cfg.loader == "bedrock")
        self.status.value = "Connecting Playit agent..."; self.status.color = COLORS["subtext"]; self._safe_update()
        ok = self.playit.start(port, bedrock, secret)
        self.status.value = "✓ Agent connected / starting." if ok else "✕ Agent failed to start. Check the output below."
        self.status.color = COLORS["accent2"] if ok else COLORS["danger"]
        if self.playit.claim_url:
            self.claim.value = f"Claim URL: {self.playit.claim_url}"
        self._safe_update()

    def _stop(self, e):
        self.playit.stop(); self.status.value = "Playit agent stopped."; self.status.color = COLORS["subtext"]; self._safe_update()

    def _create_tunnel(self, e):
        if self.playit.tunnel_address:
            self.status.value = "✓ A tunnel address is already active/saved."
            self._safe_update(); return
        if self.playit.claim_url:
            self.playit.open_claim()
            self.status.value = "Claim page opened. After claiming, Playit will finish agent registration."
        else:
            self.playit.open_tunnel_setup()
            self.status.value = "Opened the official Playit tunnel setup. Choose Minecraft Java or Bedrock and bind the selected server port."
        self._safe_update()

    def _server_changed(self, e):
        self.selected = e.control.value
        self.app.selected_server = self.selected
        self._safe_update()

    def _on_log(self, line):
        existing = self.log.value or ""
        self.log.value = (existing + line + "\n")[-12000:]
        if self.playit.claim_url:
            self.claim.value = f"Claim URL: {self.playit.claim_url}"
        if self.playit.tunnel_address:
            self.address.value = self.playit.tunnel_address
        self._safe_update()

    def _safe_update(self):
        try:
            self.app.page.update()
        except Exception:
            pass
