import threading
from pathlib import Path
import flet as ft
from src.server_manager import ServerConfig, ServerManager
from src.theme import COLORS
from src.version_fetcher import get_versions_for_loader

class CreateServerView:
    LOADERS = ["vanilla", "paper", "fabric", "forge", "bedrock"]
    ICONS = {"vanilla": "V", "paper": "P", "fabric": "F", "forge": "⚒", "bedrock": "B"}
    def __init__(self, app):
        self.app = app; self.sm = ServerManager.get(); self.versions_cache = {}; self.selected_loader = "paper"; self.selected_version = ""; self.download_url = ""; self.loader_buttons = []
        style = {"border_color": COLORS["border"], "focused_border_color": COLORS["accent"], "label_style": ft.TextStyle(color=COLORS["subtext"]), "color": COLORS["text"], "bgcolor": COLORS["surface2"]}
        self.name_field = ft.TextField(label="Server name", hint_text="My Server", **style)
        self.port_field = ft.TextField(label="Port", value="25565", width=150, **style); self.ram_field = ft.TextField(label="RAM (MB)", value="2048", width=150, **style); self.max_players_field = ft.TextField(label="Max players", value="20", width=150, **style)
        self.folder_field = ft.TextField(label="Server folder (optional)", hint_text=str(Path.home() / ".minehoster" / "servers" / "MyServer"), expand=True, **style); self.motd_field = ft.TextField(label="MOTD", value="A MineHoster Server", **style)
        self.online_mode = ft.Switch(label="Online mode", value=True, active_color=COLORS["accent"]); self.command_blocks = ft.Switch(label="Command blocks", value=False, active_color=COLORS["accent"]); self.pvp = ft.Switch(label="PvP", value=True, active_color=COLORS["accent"]); self.whitelist = ft.Switch(label="Whitelist", value=False, active_color=COLORS["accent"])
        self.difficulty_dd = ft.Dropdown(label="Difficulty", value="normal", options=[ft.dropdown.Option(v) for v in ["peaceful", "easy", "normal", "hard"]], width=180, **style); self.gamemode_dd = ft.Dropdown(label="Gamemode", value="survival", options=[ft.dropdown.Option(v) for v in ["survival", "creative", "adventure", "spectator"]], width=180, **style)
        self.version_dd = ft.Dropdown(label="Minecraft version", options=[ft.dropdown.Option("Loading...")], on_change=self._on_version_change, **style)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=11); self.download_file = ft.Text("", color=COLORS["muted"], size=11); self.progress = ft.ProgressBar(visible=False, value=0, color=COLORS["accent"], bgcolor=COLORS["surface2"]); self.create_btn = ft.ElevatedButton("Create server", bgcolor=COLORS["accent"], color=COLORS["text"], on_click=self._create, width=170)
    def build(self):
        self.loader_buttons = [self._loader_btn(loader) for loader in self.LOADERS]; self._load_versions_async(self.selected_loader)
        return ft.Container(content=ft.Column([ft.Text("New server", color=COLORS["text"], size=24, weight=ft.FontWeight.BOLD), ft.Text("Pick the server software, version and resources. MineHoster handles the setup.", color=COLORS["subtext"], size=12), ft.Container(height=12), self._section("SERVER DETAILS"), ft.Row([self.name_field, self.folder_field], spacing=10), ft.Row([self.port_field, self.max_players_field, self.ram_field], spacing=10), self.motd_field, ft.Container(height=5), self._section("SOFTWARE"), ft.Row(self.loader_buttons, spacing=7), ft.Row([self.version_dd, ft.ElevatedButton("Refresh", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=lambda e: self._load_versions_async(self.selected_loader))], spacing=8), ft.Container(height=5), self._section("GAMEPLAY"), ft.Row([self.online_mode, self.command_blocks, self.pvp, self.whitelist], spacing=18), ft.Row([self.difficulty_dd, self.gamemode_dd], spacing=10), ft.Container(height=8), self.download_file, self.progress, self.status_text, self.create_btn], spacing=9, scroll=ft.ScrollMode.AUTO, expand=True), padding=30, expand=True)
    def _section(self, title): return ft.Text(title, color=COLORS["muted"], size=10, weight=ft.FontWeight.BOLD)
    def _loader_btn(self, loader): return ft.ElevatedButton(f"{self.ICONS[loader]}  {loader.capitalize()}", bgcolor=COLORS["accent"] if loader == self.selected_loader else COLORS["surface2"], color=COLORS["text"], on_click=lambda e, value=loader: self._select_loader(value))
    def _select_loader(self, loader):
        self.selected_loader = loader; self.selected_version = ""; self.download_url = ""
        for button, value in zip(self.loader_buttons, self.LOADERS): button.bgcolor = COLORS["accent"] if value == loader else COLORS["surface2"]
        self._safe_update(); self._load_versions_async(loader)
    def _load_versions_async(self, loader):
        self.version_dd.options = [ft.dropdown.Option("Loading versions...")]; self.version_dd.value = None; self.status_text.value = f"Loading {loader.title()} versions..."; self._safe_update(); threading.Thread(target=self._load_versions, args=(loader,), daemon=True).start()
    def _load_versions(self, loader):
        try:
            if loader not in self.versions_cache: self.versions_cache[loader] = get_versions_for_loader(loader)
            versions = self.versions_cache[loader]; options = [ft.dropdown.Option(version) for version in versions]
            if options:
                self.version_dd.options = options; self.version_dd.value = options[0].key; self.selected_version = options[0].key; self.download_url = versions[self.selected_version]; self.status_text.value = f"{len(options)} versions available"
            else:
                self.version_dd.options = [ft.dropdown.Option("No versions found")]; self.version_dd.value = None; self.selected_version = ""; self.download_url = ""; self.status_text.value = f"Could not load {loader.title()} versions."; self.status_text.color = COLORS["danger"]
        except Exception as exc:
            self.version_dd.options = [ft.dropdown.Option("Version loading failed")]; self.version_dd.value = None; self.selected_version = ""; self.download_url = ""; self.status_text.value = f"Version API error: {exc}"; self.status_text.color = COLORS["danger"]
        self._safe_update()
    def _on_version_change(self, e): self.selected_version = e.control.value or ""; self.download_url = self.versions_cache.get(self.selected_loader, {}).get(self.selected_version, "")
    def _create(self, e):
        name = (self.name_field.value or "").strip()
        if not name: return self._error("Enter a server name.")
        if not self.selected_version or not self.download_url: return self._error("Select a valid Minecraft version.")
        if name in {server.name for server in self.sm.get_servers()}: return self._error("A server with that name already exists.")
        try: port, ram, max_players = int(self.port_field.value or "25565"), int(self.ram_field.value or "2048"), int(self.max_players_field.value or "20")
        except ValueError: return self._error("Port, RAM and max players must be numbers.")
        if not 1 <= port <= 65535: return self._error("Port must be between 1 and 65535.")
        if ram < 512: return self._error("RAM must be at least 512 MB.")
        if max_players < 1: return self._error("Max players must be at least 1.")
        config = ServerConfig(name=name, version=self.selected_version, loader=self.selected_loader, port=port, ram_mb=ram, folder=(self.folder_field.value or "").strip(), online_mode=bool(self.online_mode.value), command_blocks=bool(self.command_blocks.value), max_players=max_players, difficulty=self.difficulty_dd.value or "normal", gamemode=self.gamemode_dd.value or "survival", pvp=bool(self.pvp.value), whitelist=bool(self.whitelist.value), motd=(self.motd_field.value or "").strip() or "A MineHoster Server")
        self.create_btn.disabled = True; self.progress.visible = True; self.progress.value = 0; self.download_file.value = f"Preparing: {self.selected_loader.title()} {self.selected_version}"; self.status_text.value = "Preparing server..."; self._safe_update(); threading.Thread(target=self._create_worker, args=(config,), daemon=True).start()
    def _create_worker(self, config):
        def progress(stage, message, percent=None):
            self.status_text.value = message; self.status_text.color = COLORS["danger"] if stage == "error" else COLORS["subtext"]
            if stage in ("downloading", "progress") and self.selected_version: self.download_file.value = message.split("...", 1)[0]
            if percent is not None: self.progress.value = max(0, min(100, percent)) / 100
            self._safe_update()
        ok = self.sm.create_server(config, self.download_url, progress); self.progress.visible = False; self.create_btn.disabled = False
        if ok:
            self.status_text.value = "Server created. Opening dashboard..."; self.status_text.color = COLORS["accent2"]; self._safe_update(); self.app.navigate("dashboard")
        else: self._safe_update()
    def _error(self, message): self.status_text.value = f"✕ {message}"; self.status_text.color = COLORS["danger"]; self._safe_update()
    def _safe_update(self):
        try:
            self.progress.update(); self.create_btn.update(); self.status_text.update(); self.download_file.update(); self.version_dd.update()
            for button in self.loader_buttons: button.update()
        except Exception: pass
