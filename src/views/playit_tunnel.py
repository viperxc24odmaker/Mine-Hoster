from __future__ import annotations

import threading
import time
import webbrowser
import flet as ft
from src.playit import PlayitManager
from src.server_manager import ServerManager
from src.theme import COLORS

class PlayitTunnelView:
    def __init__(self, app):
        self.app = app; self.sm = ServerManager.get(); self.playit = PlayitManager.get(); self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.status = ft.Text("Ready.", color=COLORS["subtext"], size=12); self.address = ft.Text("", color=COLORS["accent2"], size=15, selectable=True, weight=ft.FontWeight.BOLD); self.claim = ft.Text("", color=COLORS["warning"], size=12, selectable=True); self.log = ft.Text("", color=COLORS["muted"], size=10, selectable=True); self.progress = ft.ProgressBar(visible=False, value=0, color=COLORS["accent"]); self.setup_code = ft.TextField(label="Optional setup code", hint_text="Leave blank for the official claim flow", expand=True)

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text(subtitle, size=12, color=COLORS["subtext"]), ft.Container(height=6), *controls], spacing=8), bgcolor=COLORS["card"], border_radius=14, padding=20, border=ft.border.all(1, COLORS["border"]))

    def build(self):
        servers = self.sm.get_servers(); dd = ft.Dropdown(value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._server_change, width=240) if servers else ft.Text("Create a server first.", color=COLORS["subtext"])
        return ft.Container(content=ft.Column([
            ft.Text("Playit.gg", size=26, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Free public tunneling for local Minecraft servers — no port forwarding.", size=13, color=COLORS["subtext"]), ft.Container(height=10),
            self._card("Tunnel target", "The local origin is always 127.0.0.1 and the selected server port.", [dd, ft.Row([ft.Button("Install / Update Agent", on_click=self._install), ft.Button("First-time Setup", on_click=self._setup), ft.Button("Connect Agent", on_click=self._connect), ft.Button("Stop Agent", on_click=self._stop)], wrap=True), self.setup_code, self.progress, self.status]),
            ft.Container(height=14), self._card("Create a free Minecraft tunnel", "Playit requires the account-side tunnel to be created after the agent is claimed. MineHoster opens the official wizard with the correct local port ready to enter.", [ft.Row([ft.Button("Create Free Tunnel", on_click=self._create_tunnel), ft.Button("Open Tunnel Dashboard", on_click=lambda e: webbrowser.open("https://playit.gg/account/tunnels"))], wrap=True), self.address, self.claim]),
            ft.Container(height=14), self._card("Agent output", "Live diagnostics and public address detection.", [self.log]),
        ], scroll=ft.ScrollMode.AUTO), padding=28, expand=True)

    def _safe(self):
        try: self.app.page.update()
        except Exception: pass
    def _server_change(self, e): self.selected = e.control.value; self._safe()
    def _install(self, e):
        self.progress.visible = True; self.progress.value = 0; self.status.value = "Installing official Playit agent..."; self._safe()
        def work():
            ok = self.playit.install(lambda _, msg, pct=None: self._progress(msg, pct)); self.status.value = "✓ Agent installed." if ok else "✕ Agent installation failed."; self.status.color = COLORS["accent2"] if ok else COLORS["danger"]; self.progress.visible = False; self._safe()
        threading.Thread(target=work, daemon=True).start()
    def _progress(self, msg, pct): self.status.value = msg; self.progress.value = pct / 100 if pct is not None else None; self._safe()
    def _setup(self, e):
        self.playit.register_callback(self._on_log); self.status.value = "Starting official Playit setup..."; self._safe()
        def work():
            ok = self.playit.setup((self.setup_code.value or "").strip()); self.status.value = "✓ Setup started. Claim the URL shown below, then connect the agent." if ok else "✕ Playit setup could not start."; self.status.color = COLORS["accent2"] if ok else COLORS["danger"]; self._safe()
        threading.Thread(target=work, daemon=True).start()
    def _connect(self, e): self._start_agent(False)
    def _create_tunnel(self, e): self._start_agent(True)
    def _start_agent(self, open_wizard=False):
        if not self.selected: self.status.value = "Select a server first."; self.status.color = COLORS["danger"]; self._safe(); return
        cfg = self.sm.servers.get(self.selected)
        if not cfg: return
        self.playit.register_callback(self._on_log); ok = self.playit.start(cfg.port, cfg.loader == "bedrock")
        if ok:
            self.status.value = f"✓ Agent connected on 127.0.0.1:{cfg.port}"; self.status.color = COLORS["accent2"]
            if open_wizard: threading.Thread(target=lambda: (time.sleep(1), webbrowser.open("https://playit.gg/account/setup/new-tunnel")), daemon=True).start()
        else: self.status.value = "✕ Agent could not connect. Run First-time Setup and claim the agent."; self.status.color = COLORS["danger"]
        self._safe()
    def _stop(self, e): self.playit.stop(); self.status.value = "Playit agent stopped."; self._safe()
    def _on_log(self, line):
        self.log.value = ((self.log.value or "") + line + "\n")[-6000:]
        if self.playit.claim_url: self.claim.value = f"Claim/setup: {self.playit.claim_url}"
        if self.playit.tunnel_address: self.address.value = f"Public address: {self.playit.tunnel_address}"
        self._safe()
