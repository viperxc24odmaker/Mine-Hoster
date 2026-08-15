from __future__ import annotations

import threading
import flet as ft
from src.playit import PlayitManager
from src.server_manager import ServerManager
from src.theme import COLORS


class PlayitView:
    """Guided Playit setup modeled around a simple connect -> claim -> tunnel flow."""
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.playit = PlayitManager.get()
        servers = self.sm.get_servers()
        self.selected = app.selected_server or (servers[0].name if servers else None)
        self.status = ft.Text("Step 1 of 3 · Ready to connect Playit.", color=COLORS["subtext"], size=12)
        self.address = ft.Text(self.playit.tunnel_address or "No tunnel created yet.", color=COLORS["accent2"], size=15, selectable=True)
        self.claim = ft.Text("", color=COLORS["warning"], size=12, selectable=True)
        self.code = ft.TextField(label="Playit code", hint_text="Paste the code Playit gave you", expand=True, autofocus=False)
        self.log = ft.TextField(value="", multiline=True, read_only=True, min_lines=6, max_lines=12, expand=True, text_size=11)
        self.secret = ft.TextField(label="Advanced: Playit secret key", password=True, can_reveal_password=True, expand=True, hint_text="Optional; not required for the guided flow")
        self.progress = ft.ProgressBar(value=0, visible=False, expand=True)
        self.playit.register_callback(self._on_log)

    def _cfg(self):
        return self.sm.servers.get(self.selected) if self.selected else None

    def build(self):
        servers = self.sm.get_servers()
        server_dd = ft.Dropdown(label="Minecraft server", value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._server_changed, width=260) if servers else ft.Text("Create a server first to bind a tunnel.", color=COLORS["subtext"])
        return ft.Container(content=ft.Column([
            ft.Row([ft.Column([ft.Text("Playit.gg", size=28, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Connect your local Minecraft server to the internet — no port forwarding.", color=COLORS["subtext"], size=13)], expand=True), server_dd]),
            self._card("1 · Connect Playit", "MineHoster downloads and starts the official Playit agent for you.", [
                ft.Row([ft.ElevatedButton("Install / Update", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._install), ft.ElevatedButton("Connect Playit", bgcolor=COLORS["accent2"], color=COLORS["bg"], on_click=self._connect)], wrap=True, spacing=8),
                self.progress, self.status,
            ]),
            self._card("2 · Verify your Playit account", "If Playit asks you to claim the agent, MineHoster will show the link. Open it, complete Playit's verification, then paste the generated code here.", [
                ft.Row([ft.ElevatedButton("Open Claim Page", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._open_claim), ft.TextButton("Open Playit", on_click=lambda e: self.playit.open_tunnel_setup())], wrap=True),
                ft.Row([self.code, ft.ElevatedButton("Submit Code", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._submit_code)], spacing=8),
                self.claim,
                ft.Text("Never share a Playit secret key. MineHoster only uses the one-time code you paste here to finish the local agent setup.", color=COLORS["muted"], size=11),
            ]),
            self._card("3 · Create your free Minecraft tunnel", "After the agent is connected, create a free tunnel for the selected server. MineHoster remembers the public address.", [
                ft.Row([ft.ElevatedButton("Create Free Tunnel", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._create_tunnel), ft.TextButton("Open Tunnel Manager", on_click=lambda e: self.playit.open_tunnel_setup())], wrap=True),
                ft.Text("Public address", color=COLORS["subtext"], size=11), self.address,
                ft.TextButton("Copy Address", on_click=self._copy_address),
            ]),
            self._card("Advanced", "Optional headless setup for users who already have a Playit secret.", [
                ft.Row([self.secret, ft.ElevatedButton("Connect with Secret", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._connect_secret)], spacing=8),
            ]),
            self._card("Agent Output", "Only useful diagnostic output is shown here; Playit runs without a Windows console window.", [self.log]),
        ], spacing=14, scroll=ft.ScrollMode.AUTO), padding=28, expand=True)

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text(subtitle, size=12, color=COLORS["subtext"]), ft.Container(height=5), *controls], spacing=8), bgcolor=COLORS["card"], border_radius=14, padding=18, border=ft.border.all(1, COLORS["border"]), expand=True)

    def _install(self, e):
        self.progress.visible = True; self.progress.value = 0; self.status.value = "Installing the official Playit agent..."; self._safe_update()
        def worker():
            ok = self.playit.install(self._progress)
            self.status.value = "✓ Agent ready. Click Connect Playit." if ok else "✕ Playit installation failed."
            self.status.color = COLORS["accent2"] if ok else COLORS["danger"]
            self.progress.visible = False; self._safe_update()
        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, stage, message, percent=0):
        self.status.value = message
        if percent is not None: self.progress.value = percent / 100
        self._safe_update()

    def _connect(self, e):
        cfg = self._cfg()
        port = cfg.port if cfg else 25565
        bedrock = bool(cfg and cfg.loader == "bedrock")
        self.status.value = "Step 2 of 3 · Starting Playit and waiting for verification..."; self.status.color = COLORS["subtext"]; self._safe_update()
        ok = self.playit.setup("")
        self.status.value = "✓ Playit agent started. Open the claim page and paste the code." if ok else "✕ Could not start Playit setup."
        self.status.color = COLORS["accent2"] if ok else COLORS["danger"]
        if self.playit.claim_url:
            self.claim.value = f"Claim URL: {self.playit.claim_url}"
        self._safe_update()

    def _open_claim(self, e):
        if self.playit.claim_url:
            self.playit.open_claim()
            self.status.value = "Step 2 of 3 · Finish Playit verification in your browser, then paste the code below."
        else:
            self.playit.open_tunnel_setup()
            self.status.value = "Step 2 of 3 · Playit setup opened. Complete verification, then return here."
        self._safe_update()

    def _submit_code(self, e):
        code = (self.code.value or "").strip()
        if not code:
            self.status.value = "Paste the Playit code first."
            self.status.color = COLORS["warning"]
            self._safe_update(); return
        ok = self.playit.setup(code)
        self.status.value = "✓ Code submitted. Waiting for Playit to finish registration..." if ok else "✕ Could not submit the code."
        self.status.color = COLORS["accent2"] if ok else COLORS["danger"]
        self._safe_update()

    def _connect_secret(self, e):
        secret = self.secret.value or ""
        if not secret.strip():
            self.status.value = "Enter a Playit secret key first."
            self.status.color = COLORS["warning"]
            self._safe_update(); return
        self.status.value = "Starting Playit with your secret..."; self._safe_update()
        ok = self.playit.start(self._cfg().port if self._cfg() else 25565, bool(self._cfg() and self._cfg().loader == "bedrock"), secret)
        self.status.value = "✓ Playit agent connected." if ok else "✕ Playit failed to start."
        self.status.color = COLORS["accent2"] if ok else COLORS["danger"]
        self._safe_update()

    def _create_tunnel(self, e):
        cfg = self._cfg()
        if not cfg:
            self.status.value = "Create/select a server first."
            self.status.color = COLORS["warning"]
            self._safe_update(); return
        if not self.playit.running:
            self.status.value = "Connect Playit first."
            self.status.color = COLORS["warning"]
            self._safe_update(); return
        self.playit.open_tunnel_setup()
        self.status.value = f"Step 3 of 3 · Tunnel setup opened for local port {cfg.port}. Choose the free Minecraft tunnel, then MineHoster will detect its public address."
        self.status.color = COLORS["subtext"]
        self._safe_update()

    def _copy_address(self, e):
        if self.playit.tunnel_address:
            try:
                self.app.page.set_clipboard(self.playit.tunnel_address)
                self.status.value = "✓ Public address copied."
            except Exception:
                self.status.value = "Select and copy the public address above."
        else:
            self.status.value = "No public tunnel address yet."
        self._safe_update()

    def _stop(self, e=None):
        self.playit.stop(); self.status.value = "Playit agent stopped."; self.status.color = COLORS["subtext"]; self._safe_update()

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
            self.status.value = "✓ Tunnel online. Your public Minecraft address is ready."
            self.status.color = COLORS["accent2"]
        self._safe_update()

    def _safe_update(self):
        try:
            self.app.page.update()
        except Exception:
            pass
