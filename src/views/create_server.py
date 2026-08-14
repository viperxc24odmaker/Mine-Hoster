import flet as ft
import threading
from pathlib import Path
from src.server_manager import ServerManager, ServerConfig
from src.version_fetcher import get_versions_for_loader
from src.theme import COLORS


class CreateServerView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.versions_cache: dict[str, dict] = {}
        self.selected_loader = "paper"
        self.selected_version = ""
        self.download_url = ""

        # UI refs
        self.name_field = ft.TextField(
            label="Server Name", hint_text="My Server",
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"],
        )
        self.port_field = ft.TextField(
            label="Port", value="25565",
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"], width=120,
        )
        self.ram_field = ft.TextField(
            label="RAM (MB)", value="2048",
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"], width=120,
        )
        self.folder_field = ft.TextField(
            label="Server Folder (optional — leave blank for default)",
            hint_text=str(Path.home() / ".minehoster" / "servers" / "MyServer"),
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"], expand=True,
        )
        self.motd_field = ft.TextField(
            label="MOTD (Server Description)", value="A MineHoster Server",
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"],
        )
        self.max_players_field = ft.TextField(
            label="Max Players", value="20",
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"], width=120,
        )

        self.online_mode = ft.Switch(label="Online Mode", value=True, active_color=COLORS["accent"])
        self.command_blocks = ft.Switch(label="Command Blocks", value=False, active_color=COLORS["accent"])
        self.pvp = ft.Switch(label="PvP", value=True, active_color=COLORS["accent"])
        self.whitelist = ft.Switch(label="Whitelist", value=False, active_color=COLORS["accent"])

        self.difficulty_dd = ft.Dropdown(
            label="Difficulty", value="normal",
            options=[ft.dropdown.Option(d) for d in ["peaceful", "easy", "normal", "hard"]],
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"], width=160,
        )
        self.gamemode_dd = ft.Dropdown(
            label="Gamemode", value="survival",
            options=[ft.dropdown.Option(g) for g in ["survival", "creative", "adventure", "spectator"]],
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"], width=160,
        )

        self.version_dd = ft.Dropdown(
            label="Version",
            options=[ft.dropdown.Option("Loading...")],
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            label_style=ft.TextStyle(color=COLORS["subtext"]),
            color=COLORS["text"], bgcolor=COLORS["surface2"],
            on_change=self._on_version_change,
        )

        self.status_text = ft.Text("", color=COLORS["subtext"], size=13)
        self.progress = ft.ProgressBar(visible=False, color=COLORS["accent"], bgcolor=COLORS["surface2"])
        self.create_btn = ft.ElevatedButton(
            "Create Server", bgcolor=COLORS["accent"], color=COLORS["text"],
            on_click=self._create, width=160,
        )

        self.loader_row = ft.Ref[ft.Row]()

    def build(self):
        loaders = ["vanilla", "paper", "fabric", "forge", "bedrock"]

        loader_buttons = ft.Row(
            ref=self.loader_row,
            controls=[self._loader_btn(l) for l in loaders],
            spacing=8,
        )

        # Load versions for default loader
        self._load_versions(self.selected_loader)

        return ft.Container(
            content=ft.Column([
                ft.Text("Create New Server", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                ft.Text("Configure and download a new Minecraft server", color=COLORS["subtext"], size=13),
                ft.Container(height=16),

                # Basic info
                self._section("Basic Info"),
                self.name_field,
                ft.Row([self.port_field, self.max_players_field, self.ram_field], spacing=12),
                self.motd_field,
                ft.Row([self.folder_field], spacing=12),

                ft.Container(height=8),
                self._section("Server Type"),
                loader_buttons,
                ft.Container(height=8),
                self.version_dd,

                ft.Container(height=8),
                self._section("Server Options"),
                ft.Row([self.online_mode, self.command_blocks, self.pvp, self.whitelist], spacing=24),
                ft.Row([self.difficulty_dd, self.gamemode_dd], spacing=12),

                ft.Container(height=16),
                self.progress,
                self.status_text,
                ft.Container(height=8),
                self.create_btn,
            ], scroll=ft.ScrollMode.AUTO, spacing=12),
            padding=32,
            expand=True,
        )

    def _section(self, title):
        return ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=COLORS["subtext"])

    def _loader_btn(self, loader: str):
        is_active = loader == self.selected_loader
        icons = {"vanilla": "🌿", "paper": "📄", "fabric": "🧵", "forge": "⚒️", "bedrock": "🪨"}

        def on_click(e, l=loader):
            self.selected_loader = l
            self._refresh_loader_buttons()
            self._load_versions(l)

        return ft.ElevatedButton(
            f"{icons.get(loader, '')} {loader.capitalize()}",
            bgcolor=COLORS["accent"] if is_active else COLORS["surface2"],
            color=COLORS["text"],
            on_click=on_click,
        )

    def _refresh_loader_buttons(self):
        if self.loader_row.current:
            loaders = ["vanilla", "paper", "fabric", "forge", "bedrock"]
            icons = {"vanilla": "🌿", "paper": "📄", "fabric": "🧵", "forge": "⚒️", "bedrock": "🪨"}
            for i, btn in enumerate(self.loader_row.current.controls):
                l = loaders[i]
                btn.bgcolor = COLORS["accent"] if l == self.selected_loader else COLORS["surface2"]
            try:
                self.loader_row.current.update()
            except Exception:
                pass

    def _load_versions(self, loader: str):
        self.version_dd.options = [ft.dropdown.Option("Loading versions...")]
        self.version_dd.value = None
        try:
            self.version_dd.update()
        except Exception:
            pass

        def fetch():
            try:
                if loader not in self.versions_cache:
                    self.versions_cache[loader] = get_versions_for_loader(loader)
                versions = self.versions_cache[loader]
                opts = [ft.dropdown.Option(v) for v in versions.keys()]
                self.version_dd.options = opts
                if opts:
                    self.version_dd.value = opts[0].key
                    self.selected_version = opts[0].key
                    self.download_url = versions.get(self.selected_version, "")
                    # Bedrock: server_manager uses its own internal URL
                    if loader == "bedrock" and self.selected_version:
                        self.download_url = self.selected_version
                else:
                    self.version_dd.options = [ft.dropdown.Option("No versions found")]
            except Exception as ex:
                self.version_dd.options = [ft.dropdown.Option(f"Error: {ex}")]
            try:
                self.version_dd.update()
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    def _on_version_change(self, e):
        self.selected_version = e.control.value or ""
        versions = self.versions_cache.get(self.selected_loader, {})
        self.download_url = versions.get(self.selected_version, "")
        # Bedrock uses a fixed internal URL, so any version selection is valid
        if self.selected_loader == "bedrock" and self.selected_version:
            self.download_url = self.selected_version  # non-empty sentinel

    def _create(self, e):
        name = self.name_field.value.strip()
        if not name:
            self.status_text.value = "❌ Please enter a server name"
            self.status_text.color = COLORS["danger"]
            self.status_text.update()
            return
        if not self.selected_version or not self.download_url:
            self.status_text.value = "❌ Please select a version"
            self.status_text.color = COLORS["danger"]
            self.status_text.update()
            return
        if name in {s.name for s in self.sm.get_servers()}:
            self.status_text.value = "❌ A server with that name already exists"
            self.status_text.color = COLORS["danger"]
            self.status_text.update()
            return

        try:
            port = int(self.port_field.value or 25565)
            ram = int(self.ram_field.value or 2048)
            max_players = int(self.max_players_field.value or 20)
        except ValueError:
            self.status_text.value = "❌ Port, RAM and Max Players must be numbers"
            self.status_text.color = COLORS["danger"]
            self.status_text.update()
            return

        config = ServerConfig(
            name=name,
            version=self.selected_version,
            loader=self.selected_loader,
            port=port,
            ram_mb=ram,
            folder=self.folder_field.value.strip(),
            online_mode=self.online_mode.value,
            command_blocks=self.command_blocks.value,
            max_players=max_players,
            difficulty=self.difficulty_dd.value,
            gamemode=self.gamemode_dd.value,
            pvp=self.pvp.value,
            whitelist=self.whitelist.value,
            motd=self.motd_field.value.strip() or "A MineHoster Server",
        )

        self.create_btn.disabled = True
        self.progress.visible = True
        self.create_btn.update()
        self.progress.update()

        def do_create():
            def cb(stage, msg):
                self.status_text.value = msg
                self.status_text.color = COLORS["danger"] if stage == "error" else COLORS["subtext"]
                try:
                    self.status_text.update()
                except Exception:
                    pass

            ok = self.sm.create_server(config, self.download_url, cb)
            self.progress.visible = False
            self.create_btn.disabled = False
            try:
                self.progress.update()
                self.create_btn.update()
            except Exception:
                pass
            if ok:
                self.status_text.value = "✅ Server created successfully!"
                self.status_text.color = COLORS["accent2"]
                try:
                    self.status_text.update()
                except Exception:
                    pass
                self.app.navigate("dashboard")

        threading.Thread(target=do_create, daemon=True).start()
