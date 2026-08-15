import json
import random
import shutil
import threading
from pathlib import Path
import flet as ft
from src.server_manager import ServerManager, SERVERS_FILE
from src.version_fetcher import clear_cache
from src.java_runtime import download_java, installed_jres
from src.theme import COLORS, ACCENT_PRESETS

PREFS_FILE = SERVERS_FILE.parent / "preferences.json"


class SettingsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        servers = self.sm.get_servers()
        self.selected = app.selected_server or (servers[0].name if servers else None)
        self.status_text = ft.Text("", color=COLORS["subtext"], size=12)
        self.props_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.prop_fields = {}
        self.jre_status = ft.Text("", color=COLORS["subtext"], size=12)
        self.jre_progress = ft.ProgressBar(value=0, visible=False, color=COLORS["accent"])
        self.world_status = ft.Text("", color=COLORS["subtext"], size=12)
        self.appearance_status = ft.Text("", color=COLORS["subtext"], size=12)

    def _prefs(self):
        try:
            data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_prefs(self, data):
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PREFS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(PREFS_FILE)

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]), ft.Text(subtitle, color=COLORS["subtext"], size=12), ft.Container(height=8), *controls], spacing=8), bgcolor=COLORS["card"], border_radius=12, padding=20, border=ft.border.all(1, COLORS["border"]))

    def build(self):
        prefs = self._prefs()
        accent = prefs.get("accent", "Graphite") if prefs.get("accent", "Graphite") in ACCENT_PRESETS else "Graphite"
        mode = prefs.get("mode", "dark")
        accent_dd = ft.Dropdown(label="Accent", value=accent, options=[ft.dropdown.Option(k) for k in ACCENT_PRESETS], width=180)
        mode_dd = ft.Dropdown(label="Appearance", value=mode, options=[ft.dropdown.Option("dark"), ft.dropdown.Option("light"), ft.dropdown.Option("system")], width=180)
        servers = self.sm.get_servers()
        if servers:
            server_dd = ft.Dropdown(label="Server", value=self.selected, options=[ft.dropdown.Option(s.name) for s in servers], on_change=self._on_server_change, width=220, color=COLORS["text"], bgcolor=COLORS["surface2"], border_color=COLORS["border"])
            self._load_props()
            server_controls = [server_dd, self.props_col, ft.Row([ft.ElevatedButton("Save Server Properties", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=self._save_props), self.status_text], spacing=12)]
        else:
            server_controls = [ft.Text("No servers found. Create one from New Server.", color=COLORS["subtext"])]

        def save_appearance(e):
            chosen = accent_dd.value or "Graphite"
            if chosen not in ACCENT_PRESETS: chosen = "Graphite"
            base, soft = ACCENT_PRESETS[chosen]
            COLORS["accent"] = base; COLORS["accent_soft"] = soft
            COLORS["accent2_soft"] = COLORS["accent2"] + "1C"
            selected_mode = mode_dd.value or "dark"
            if selected_mode == "light":
                COLORS.update({"bg": "#F3F5F7", "surface": "#FFFFFF", "surface2": "#EEF1F4", "card": "#FFFFFF", "border": "#D8DEE6", "text": "#151A21", "subtext": "#5D6673", "muted": "#7A8491"})
            else:
                COLORS.update({"bg": "#090B0F", "surface": "#101319", "surface2": "#171B22", "card": "#13171E", "border": "#2A303A", "text": "#F4F6F8", "subtext": "#A0A8B5", "muted": "#68717E"})
            self._save_prefs({"accent": chosen, "mode": selected_mode})
            self.app.page.bgcolor = COLORS["bg"]
            self.appearance_status.value = "✓ Appearance saved. MineHoster will refresh the interface."
            self.appearance_status.color = COLORS["accent2"]
            self._safe_update()
            self.app.navigate("settings")

        appearance = self._card("Appearance", "Customize MineHoster without losing the neutral default.", [ft.Row([accent_dd, mode_dd], wrap=True), ft.ElevatedButton("Save Appearance", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=save_appearance), self.appearance_status])
        jre_buttons = [ft.ElevatedButton(f"Download JRE {v}", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=lambda e, version=v: self._download_jre(version)) for v in (17, 21, 25)]
        jre = self._card("Java Runtime Manager", "MineHoster automatically selects a compatible private JRE for each Minecraft version.", [ft.Row(jre_buttons, wrap=True), self.jre_progress, self.jre_status, self._installed_jres_text()])
        world = self._card("World Management", "Generate and apply a seed or reset the selected server world.", [ft.Row([ft.TextField(label="World seed", expand=True, value=self.sm.get_properties(self.selected).get("level-seed", "") if self.selected else ""), ft.ElevatedButton("Generate Seed", on_click=self._generate_seed)], wrap=True), ft.Row([ft.ElevatedButton("Reset World", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._reset_world), self.world_status])])
        maintenance = self._card("Maintenance", "Refresh metadata or remove the selected server.", [ft.Row([ft.ElevatedButton("Refresh Version Cache", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._clear_cache), ft.Text("Re-fetch Minecraft and loader version lists.", color=COLORS["subtext"], size=12)]), ft.Row([ft.ElevatedButton("Delete Selected Server", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._delete_server), ft.Text("Permanently deletes the selected server and files.", color=COLORS["danger"], size=12)])])
        return ft.Container(content=ft.Column([ft.Text("Server Settings", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text("Everything here is editable; changes are written to local MineHoster data.", color=COLORS["subtext"], size=13), ft.Container(height=16), appearance, ft.Container(height=14), self._card("Server Properties", "Edit the actual server.properties file for the selected server.", server_controls), ft.Container(height=14), jre, ft.Container(height=14), world, ft.Container(height=14), maintenance], scroll=ft.ScrollMode.AUTO), padding=32, expand=True)

    def _load_props(self):
        if not self.selected: return
        props = self.sm.get_properties(self.selected); self.props_col.controls.clear(); self.prop_fields.clear()
        priority = ["server-port", "level-seed", "online-mode", "enable-command-block", "max-players", "difficulty", "gamemode", "pvp", "white-list", "motd", "view-distance", "spawn-protection", "allow-flight", "allow-nether"]
        for key in [k for k in priority if k in props] + [k for k in props if k not in priority]:
            field = ft.TextField(label=key, value=props[key], border_color=COLORS["border"], focused_border_color=COLORS["accent"], label_style=ft.TextStyle(color=COLORS["subtext"]), color=COLORS["text"], bgcolor=COLORS["surface2"])
            self.prop_fields[key] = field; self.props_col.controls.append(field)

    def _on_server_change(self, e):
        self.selected = e.control.value; self.app.selected_server = self.selected; self._load_props(); self._safe_update()

    def _save_props(self, e):
        if not self.selected: return
        if self.sm.is_running(self.selected):
            self.status_text.value = "Stop the server before changing server.properties."; self.status_text.color = COLORS["warning"]; self._safe_update(); return
        ok = self.sm.update_properties(self.selected, {k: f.value for k, f in self.prop_fields.items()})
        self.status_text.value = "✓ Server properties saved." if ok else "✕ Could not save server properties."; self.status_text.color = COLORS["accent2"] if ok else COLORS["danger"]; self._safe_update()

    def _installed_jres_text(self):
        installed = installed_jres(); text = ", ".join(f"Java {v}" for v, _, _ in installed) if installed else "No private JREs downloaded yet."; return ft.Text(f"Installed: {text}", color=COLORS["muted"], size=11)

    def _download_jre(self, version):
        self.jre_progress.visible = True; self.jre_progress.value = 0; self.jre_status.value = f"Preparing JRE {version}..."; self._safe_update()
        def worker():
            try:
                def progress(stage, message, percent=None):
                    self.jre_status.value = message
                    if percent is not None: self.jre_progress.value = percent / 100
                    self._safe_update()
                download_java(version, progress); self.jre_status.value = f"✓ JRE {version} is ready."; self.jre_status.color = COLORS["accent2"]
            except Exception as exc: self.jre_status.value = f"✕ JRE {version} failed: {exc}"; self.jre_status.color = COLORS["danger"]
            finally: self.jre_progress.visible = False; self._safe_update()
        threading.Thread(target=worker, daemon=True).start()

    def _generate_seed(self, e):
        self.status_text.value = str(random.randint(-(2**63), 2**63 - 1)); self.status_text.color = COLORS["accent2"]; self._safe_update()

    def _reset_world(self, e):
        if not self.selected: return
        if self.sm.is_running(self.selected): self.world_status.value = "✕ Stop the server before resetting its world."; self.world_status.color = COLORS["danger"]; self._safe_update(); return
        cfg = self.sm.servers.get(self.selected)
        if not cfg: return
        removed = []
        for name in ("world", "world_nether", "world_the_end"):
            path = Path(cfg.folder) / name
            if path.exists(): shutil.rmtree(path, ignore_errors=True); removed.append(name)
        self.world_status.value = "✓ World reset: " + (", ".join(removed) if removed else "no world folders existed yet"); self.world_status.color = COLORS["accent2"]; self._safe_update()

    def _clear_cache(self, e): clear_cache(); self.status_text.value = "✓ Version cache cleared."; self._safe_update()

    def _delete_server(self, e):
        if self.selected: self.sm.delete_server(self.selected); self.selected = None; self.app.selected_server = None; self.app.navigate("dashboard")

    def _safe_update(self):
        try: self.app.page.update()
        except Exception: pass
