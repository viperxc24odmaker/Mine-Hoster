from __future__ import annotations

import json
import shutil
import threading
import zipfile
from datetime import datetime
from pathlib import Path
import flet as ft
from src.server_manager import ServerManager, SERVERS_DIR
from src.theme import COLORS

CONFIG = Path.home() / ".minehoster" / "hosting.json"
DEFAULT = {"backup_enabled": True, "backup_time": "03:00", "backup_keep": 7, "restart_enabled": False, "restart_time": "04:00", "restart_warn": 60}


def load_cfg():
    try:
        raw = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
        return {**DEFAULT, **(raw if isinstance(raw, dict) else {})}
    except Exception:
        return dict(DEFAULT)


def save_cfg(data):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp"); tmp.write_text(json.dumps(data, indent=2), encoding="utf-8"); tmp.replace(CONFIG)


class HostingSettingsViewV2:
    def __init__(self, app):
        self.app = app; self.sm = ServerManager.get(); self.cfg = load_cfg()
        self.server = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.status = ft.Text("Schedules run locally while MineHoster is open.", color=COLORS["subtext"], size=12)
        self.backup = ft.Switch(label="Automatic backups", value=bool(self.cfg["backup_enabled"]))
        self.backup_time = ft.TextField(label="Backup time (HH:MM)", value=self.cfg["backup_time"], width=160)
        self.keep = ft.TextField(label="Backups to keep", value=str(self.cfg["backup_keep"]), width=150)
        self.restart = ft.Switch(label="Automatic server restart", value=bool(self.cfg["restart_enabled"]))
        self.restart_time = ft.TextField(label="Restart time (HH:MM)", value=self.cfg["restart_time"], width=160)
        self.warn = ft.TextField(label="Warning seconds", value=str(self.cfg["restart_warn"]), width=150)

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]), ft.Text(subtitle, size=12, color=COLORS["subtext"]), ft.Container(height=6), *controls]), bgcolor=COLORS["card"], border_radius=14, padding=20, border=ft.border.all(1, COLORS["border"]))

    def build(self):
        servers = self.sm.get_servers()
        dd = ft.Dropdown(value=self.server, options=[ft.dropdown.Option(s.name) for s in servers], on_change=lambda e: self._select(e), width=220) if servers else ft.Text("No servers yet.", color=COLORS["subtext"])
        return ft.Container(content=ft.Column([
            ft.Text("Hosting Settings", size=26, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            ft.Text("Automation, storage, recovery and local hosting controls.", size=13, color=COLORS["subtext"]),
            ft.Container(height=10),
            self._card("Server automation", "MineHoster performs these tasks only while the desktop app is running.", [dd, self.backup, ft.Row([self.backup_time, self.keep], wrap=True), self.restart, ft.Row([self.restart_time, self.warn], wrap=True), ft.Row([ft.Button("Save Schedule", on_click=self._save), self.status], wrap=True)]),
            ft.Container(height=14),
            self._card("Storage", "MineHoster keeps servers under the default local directory unless a server has its own custom folder.", [ft.Text(f"Default: {SERVERS_DIR}", color=COLORS["muted"], size=11, selectable=True), ft.Text(f"Managed servers: {len(servers)}", color=COLORS["subtext"])]),
            ft.Container(height=14),
            self._card("Recovery", "Create an immediate verified ZIP backup before risky maintenance.", [ft.Button("Backup Selected Server Now", on_click=self._backup_now), ft.Button("Open Server Dashboard", on_click=lambda e: self.app.navigate("dashboard"))]),
        ], scroll=ft.ScrollMode.AUTO), padding=28, expand=True)

    def _select(self, e): self.server = e.control.value; self._safe()

    def _save(self, e):
        try:
            datetime.strptime(self.backup_time.value.strip(), "%H:%M"); datetime.strptime(self.restart_time.value.strip(), "%H:%M")
            keep = max(1, int(self.keep.value)); warn = max(0, int(self.warn.value))
        except ValueError:
            self.status.value = "✕ Use valid HH:MM times and whole numbers."; self.status.color = COLORS["danger"]; self._safe(); return
        self.cfg.update({"backup_enabled": self.backup.value, "backup_time": self.backup_time.value.strip(), "backup_keep": keep, "restart_enabled": self.restart.value, "restart_time": self.restart_time.value.strip(), "restart_warn": warn}); save_cfg(self.cfg)
        self.status.value = "✓ Schedule saved."; self.status.color = COLORS["accent2"]; self._safe()

    def _backup_now(self, e):
        if not self.server: return
        cfg = self.sm.servers.get(self.server)
        if not cfg: return
        def work():
            try:
                root = Path(cfg.folder); out_dir = Path.home() / ".minehoster" / "backups" / cfg.name; out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / f"{cfg.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
                with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                    for p in root.rglob("*"):
                        if p.is_file() and ".minehoster" not in str(p): z.write(p, p.relative_to(root))
                with zipfile.ZipFile(out, "r") as z: bad = z.testzip()
                if bad: raise RuntimeError(f"Backup verification failed: {bad}")
                self.status.value = f"✓ Backup created: {out.name}"; self.status.color = COLORS["accent2"]
            except Exception as exc:
                self.status.value = f"✕ Backup failed: {exc}"; self.status.color = COLORS["danger"]
            self._safe()
        threading.Thread(target=work, daemon=True).start()

    def _safe(self):
        try: self.app.page.update()
        except Exception: pass
