import random
import shutil
import threading
from pathlib import Path

import flet as ft

from src.server_manager import ServerManager
from src.version_fetcher import clear_cache
from src.java_runtime import download_java, installed_jres
from src.playit import PlayitManager
from src.theme import COLORS


class SettingsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.playit = PlayitManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        style = dict(border_color=COLORS["border"], focused_border_color=COLORS["accent"], label_style=ft.TextStyle(color=COLORS["subtext"]), color=COLORS["text"], bgcolor=COLORS["surface2"])
        self.props_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)
        self.prop_fields = {}
        self.jre_status = ft.Text("", color=COLORS["subtext"], size=12)
        self.jre_progress = ft.ProgressBar(value=0, visible=False, color=COLORS["accent"], bgcolor=COLORS["surface2"])
        self.playit_code = ft.TextField(label="Playit setup / claim code", hint_text="Paste the code from playit.gg", expand=True, **style)
        self.playit_status = ft.Text("", color=COLORS["subtext"], size=12)
        self.playit_progress = ft.ProgressBar(value=0, visible=False, color=COLORS["accent"], bgcolor=COLORS["surface2"])
        self.playit_address = ft.Text("", color=COLORS["accent2"], size=12, selectable=True)
        self.seed_field = ft.TextField(label="World seed", hint_text="Blank = random/default", expand=True, **style)
        self.world_status = ft.Text("", color=COLORS["subtext"], size=12)

    def build(self):
        servers = self.sm.get_servers()
        if servers:
            server_inner = [
                ft.Dropdown(value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._on_server_change, border_color=COLORS["border"], focused_border_color=COLORS["accent"], color=COLORS["text"], bgcolor=COLORS["surface2"], width=220),
                ft.Container(height=8), self.props_col, ft.Container(height=8),
                ft.Row([ft.ElevatedButton("Save Properties", bgcolor=COLORS["accent2"], color=COLORS["text"], on_click=self._save_props), self.status_text], spacing=12),
            ]
        else:
            server_inner = [ft.Text("No servers found.", color=COLORS["subtext"], size=13)]

        server_section = self._card("Server Properties", "Edit server.properties for the selected server", server_inner)
        jre_buttons = [ft.ElevatedButton(f"Download JRE {version}", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=lambda e, v=version: self._download_jre(v)) for version in (17, 21, 25)]
        jre_section = self._card("Java / JRE Download Manager", "Private Eclipse Temurin runtimes are reused automatically when already installed.", [ft.Row(jre_buttons, spacing=8), self.jre_progress, self.jre_status, self._installed_jres_text()])

        playit_section = self._card("Playit.gg Tunnel", "MineHoster now uses the official Playit agent setup instead of generating an invalid custom TOML config.", [
            ft.Row([
                ft.ElevatedButton("Install / Update Agent", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._install_playit),
                ft.ElevatedButton("Start Agent", bgcolor=COLORS["accent2"], color=COLORS["text"], on_click=self._start_playit),
                ft.ElevatedButton("Stop Agent", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._stop_playit),
            ], spacing=8, wrap=True),
            ft.Row([self.playit_code, ft.ElevatedButton("Setup", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=self._setup_playit)], spacing=8),
            self.playit_progress, self.playit_status, self.playit_address,
            ft.Text("After setup, claim the agent at the URL shown by Playit, then create a Minecraft Java/Bedrock tunnel in your Playit account. MineHoster reuses the installed agent and its credentials.", color=COLORS["muted"], size=11),
        ])

        world_section = self._card("World Management", "Generate a seed or completely reset the selected server's world.", [
            ft.Row([self.seed_field, ft.ElevatedButton("Generate Seed", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._generate_seed), ft.ElevatedButton("Apply Seed", bgcolor=COLORS["accent2"], color=COLORS["text"], on_click=self._apply_seed)], spacing=8, wrap=True),
            ft.Row([ft.ElevatedButton("Reset World", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._reset_world), self.world_status], spacing=10),
        ])

        app_section = self._card("Application", "Maintenance and destructive server actions.", [
            ft.Row([ft.ElevatedButton("Refresh Version Cache", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._clear_cache), ft.Text("Re-fetch Minecraft/Paper/Fabric version lists.", color=COLORS["subtext"], size=12)], spacing=12),
            ft.Row([ft.ElevatedButton("Delete Selected Server", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._delete_server), ft.Text("Permanently deletes the server and all files.", color=COLORS["danger"], size=12)], spacing=12),
        ])

        if self.selected:
            self._load_props()
            self._load_seed()

        return ft.Container(content=ft.Column([
            ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            ft.Text("Configure servers, Java runtimes, Playit tunnels and worlds.", color=COLORS["subtext"], size=13),
            ft.Container(height=16), server_section, ft.Container(height=16), jre_section, ft.Container(height=16), playit_section, ft.Container(height=16), world_section, ft.Container(height=16), app_section,
        ], scroll=ft.ScrollMode.AUTO), padding=32, expand=True)

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]), ft.Text(subtitle, color=COLORS["subtext"], size=12), ft.Container(height=8)] + controls), bgcolor=COLORS["card"], border_radius=12, padding=20, border=ft.border.all(1, COLORS["border"]))

    def _installed_jres_text(self):
        installed = installed_jres()
        text = ", ".join(f"Java {version}" for version, _, _ in installed) if installed else "No private JREs downloaded yet."
        return ft.Text(f"Installed private runtimes: {text}", color=COLORS["muted"], size=11)

    def _download_jre(self, version):
        self.jre_progress.visible = True; self.jre_progress.value = 0; self.jre_status.value = f"Preparing JRE {version}..."; self._safe_update()
        def worker():
            def progress(stage, message, percent=None):
                self.jre_status.value = message
                if percent is not None: self.jre_progress.value = percent / 100
                self._safe_update()
            try:
                download_java(version, progress); self.jre_progress.value = 1; self.jre_status.color = COLORS["accent2"]; self.jre_status.value = f"✓ JRE {version} is ready and will be reused."
            except Exception as exc:
                self.jre_status.color = COLORS["danger"]; self.jre_status.value = f"✕ JRE {version} failed: {exc}"
            finally:
                self.jre_progress.visible = False; self._safe_update()
        threading.Thread(target=worker, daemon=True).start()

    def _install_playit(self, e):
        self.playit_progress.visible = True; self.playit_progress.value = 0; self.playit_status.value = "Downloading/checking Playit agent..."; self._safe_update()
        def worker():
            def progress(stage, message, percent=0):
                self.playit_status.value = message
                if percent is not None: self.playit_progress.value = percent / 100
                self._safe_update()
            ok = self.playit.install(progress)
            self.playit_status.color = COLORS["accent2"] if ok else COLORS["danger"]
            self.playit_status.value = "✓ Playit agent ready." if ok else "✕ Playit agent installation failed."
            self.playit_progress.visible = False; self._safe_update()
        threading.Thread(target=worker, daemon=True).start()

    def _setup_playit(self, e):
        self.playit_status.value = "Starting official Playit setup..."; self.playit_status.color = COLORS["subtext"]; self._safe_update()
        code = (self.playit_code.value or "").strip()
        def worker():
            self.playit.register_callback(self._playit_log)
            ok = self.playit.setup(code)
            self.playit_status.value = "✓ Setup process started. Follow the Playit claim/setup page shown below." if ok else "✕ Could not start Playit setup."
            self._safe_update()
        threading.Thread(target=worker, daemon=True).start()

    def _playit_log(self, line):
        if self.playit.claim_url: self.playit_status.value = f"Claim/setup URL: {self.playit.claim_url}"
        if self.playit.tunnel_address: self.playit_address.value = f"Public address: {self.playit.tunnel_address}"
        self._safe_update()

    def _start_playit(self, e):
        port = 25565; bedrock = False
        if self.selected:
            cfg = self.sm.servers.get(self.selected)
            if cfg: port = cfg.port; bedrock = cfg.loader == "bedrock"
        ok = self.playit.start(port, bedrock)
        self.playit_status.color = COLORS["accent2"] if ok else COLORS["danger"]
        self.playit_status.value = "✓ Playit agent started. Existing agent credentials are reused." if ok else "✕ Playit agent could not start."
        self._safe_update()

    def _stop_playit(self, e):
        self.playit.stop(); self.playit_status.value = "Playit agent stopped."; self._safe_update()

    def _load_props(self):
        if not self.selected: return
        props = self.sm.get_properties(self.selected); self.props_col.controls.clear(); self.prop_fields.clear()
        priority = ["server-port", "level-seed", "online-mode", "enable-command-block", "max-players", "difficulty", "gamemode", "pvp", "white-list", "motd", "view-distance", "spawn-protection", "allow-flight", "allow-nether"]
        for key in [k for k in priority if k in props] + [k for k in props if k not in priority]:
            field = ft.TextField(label=key, value=props[key], border_color=COLORS["border"], focused_border_color=COLORS["accent"], label_style=ft.TextStyle(color=COLORS["subtext"]), color=COLORS["text"], bgcolor=COLORS["surface2"])
            self.prop_fields[key] = field; self.props_col.controls.append(field)

    def _load_seed(self):
        props = self.sm.get_properties(self.selected) if self.selected else {}
        self.seed_field.value = props.get("level-seed", "")

    def _save_props(self, e):
        if not self.selected: return
        self.sm.update_properties(self.selected, {key: field.value for key, field in self.prop_fields.items()}); self.status_text.value = "✓ Saved!"; self.status_text.color = COLORS["accent2"]; self._safe_update()

    def _generate_seed(self, e):
        self.seed_field.value = str(random.randint(-(2**63), 2**63 - 1)); self._safe_update()

    def _apply_seed(self, e):
        if not self.selected: return
        seed = (self.seed_field.value or "").strip()
        self.sm.update_properties(self.selected, {"level-seed": seed})
        self.world_status.value = "✓ Seed saved. Reset the world to generate a new world from it."; self.world_status.color = COLORS["accent2"]; self._safe_update()

    def _reset_world(self, e):
        if not self.selected: return
        if self.sm.is_running(self.selected):
            self.world_status.value = "✕ Stop the server before resetting its world."; self.world_status.color = COLORS["danger"]; self._safe_update(); return
        cfg = self.sm.servers.get(self.selected)
        if not cfg: return
        folder = Path(cfg.folder)
        removed = []
        for name in ("world", "world_nether", "world_the_end"):
            path = folder / name
            if path.exists():
                shutil.rmtree(path, ignore_errors=True); removed.append(name)
        self.world_status.color = COLORS["accent2"]
        self.world_status.value = "✓ World reset: " + (", ".join(removed) if removed else "no world folders existed yet")
        self._safe_update()

    def _on_server_change(self, e):
        self.selected = e.control.value; self._load_props(); self._load_seed(); self._safe_update()

    def _clear_cache(self, e):
        clear_cache(); e.control.text = "✓ Cache Cleared"; self._safe_update()

    def _delete_server(self, e):
        if self.selected:
            self.sm.delete_server(self.selected); self.selected = None; self.app.selected_server = None; self.app.navigate("dashboard")

    def _safe_update(self):
        for control in (self.jre_progress, self.jre_status, self.playit_progress, self.playit_status, self.playit_address, self.seed_field, self.world_status, self.status_text):
            try: control.update()
            except Exception: pass
