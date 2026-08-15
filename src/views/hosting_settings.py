import shutil
import threading
from pathlib import Path
import flet as ft
from src.server_manager import ServerManager, SERVERS_FILE
from src.java_runtime import RUNTIMES_DIR
from src.scheduler import MineHosterScheduler
from src.theme import COLORS

DATA_ROOT = SERVERS_FILE.parent


class HostingSettingsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.scheduler = MineHosterScheduler.get()
        self.status = ft.Text("", color=COLORS["subtext"], size=12)
        self.resetting = False

    def _card(self, title, subtitle, controls):
        return ft.Container(content=ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]), ft.Text(subtitle, color=COLORS["subtext"], size=12), ft.Container(height=8), *controls], spacing=8), bgcolor=COLORS["card"], border_radius=12, padding=20, border=ft.border.all(1, COLORS["border"]))

    def _server_dropdown(self, value, on_change):
        return ft.Dropdown(label="Server", value=value, options=[ft.dropdown.Option(s.name) for s in self.sm.get_servers()], width=220, on_change=on_change, color=COLORS["text"], bgcolor=COLORS["surface2"], border_color=COLORS["border"])

    def build(self):
        servers = self.sm.get_servers()
        server_count = len(servers)
        selected = self.app.selected_server or (servers[0].name if servers else None)
        b = self.scheduler.get_job(selected, "backup") if selected else {}
        r = self.scheduler.get_job(selected, "restart") if selected else {}
        backup_time = ft.TextField(label="Daily backup time (HH:MM)", value=b.get("time", "03:00"), width=190)
        restart_time = ft.TextField(label="Daily restart time (HH:MM)", value=r.get("time", "06:00"), width=190)
        keep_field = ft.TextField(label="Backups to keep", value=str(b.get("keep", 7)), width=150)
        backup_switch = ft.Switch(label="Automatic backups", value=bool(b.get("enabled")))
        restart_switch = ft.Switch(label="Automatic restart", value=bool(r.get("enabled")))
        schedule_server = self._server_dropdown(selected, lambda e: self._load_schedule(e.control.value, backup_time, restart_time, keep_field, backup_switch, restart_switch)) if servers else ft.Text("Create a server to configure schedules.", color=COLORS["subtext"])

        def save_schedule(e):
            if not selected:
                self.status.value = "Create a server first."; self.status.color = COLORS["warning"]; self._safe_update(); return
            try:
                if not self._valid_time(backup_time.value) or not self._valid_time(restart_time.value): raise ValueError("Times must use 24-hour HH:MM format.")
                keep = max(1, int(keep_field.value or 7))
                self.scheduler.set_job(selected, "backup", backup_switch.value, backup_time.value.strip(), keep)
                self.scheduler.set_job(selected, "restart", restart_switch.value, restart_time.value.strip(), keep)
                self.scheduler.start()
                self.status.value = "✓ Schedule saved. MineHoster checks it in the background."; self.status.color = COLORS["accent2"]
            except Exception as exc:
                self.status.value = f"✕ {exc}"; self.status.color = COLORS["danger"]
            self._safe_update()

        return ft.Container(content=ft.Column([
            ft.Text("MineHoster Settings", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            ft.Text("Local hosting paths, scheduled maintenance, recovery and cleanup.", color=COLORS["subtext"], size=13),
            ft.Container(height=16),
            self._card("Hosting Core", "MineHoster keeps server data and private Java runtimes locally on this PC.", [ft.Text(f"Data folder: {DATA_ROOT}", color=COLORS["muted"], size=11, selectable=True), ft.Text(f"Managed servers: {server_count}", color=COLORS["subtext"], size=12), ft.Text(f"Java runtime cache: {RUNTIMES_DIR}", color=COLORS["muted"], size=11, selectable=True)]),
            ft.Container(height=14),
            self._card("Automatic Maintenance", "Schedule backups and graceful restarts without keeping another script running.", [schedule_server, ft.Row([backup_switch, backup_time, keep_field], wrap=True), ft.Row([restart_switch, restart_time], wrap=True), ft.ElevatedButton("Save Schedule", bgcolor=COLORS["accent"], color=COLORS["bg"], on_click=save_schedule), self.status]),
            ft.Container(height=14),
            self._card("Server Data", "Open the main dashboard to manage individual server locations and files.", [ft.ElevatedButton("Open Server Dashboard", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=lambda e: self.app.navigate("dashboard"))]),
            ft.Container(height=14),
            self._card("Full Reset", "Danger zone. Removes MineHoster's managed data, including servers, private JREs and schedules. The application itself remains installed.", [ft.Text("This action cannot be undone.", color=COLORS["danger"], size=12, weight=ft.FontWeight.BOLD), ft.ElevatedButton("FULL RESET MINEHOSTER", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._confirm_reset)]),
        ], scroll=ft.ScrollMode.AUTO), padding=32, expand=True)

    def _load_schedule(self, server, backup_time, restart_time, keep_field, backup_switch, restart_switch):
        self.app.selected_server = server
        b = self.scheduler.get_job(server, "backup"); r = self.scheduler.get_job(server, "restart")
        backup_time.value = b.get("time", "03:00"); keep_field.value = str(b.get("keep", 7)); backup_switch.value = bool(b.get("enabled")); restart_time.value = r.get("time", "06:00"); restart_switch.value = bool(r.get("enabled")); self._safe_update()

    @staticmethod
    def _valid_time(value):
        parts = (value or "").strip().split(":")
        return len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and 0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59

    def _confirm_reset(self, e):
        confirm = ft.TextField(label="Type RESET to confirm", width=300, autofocus=True)
        dialog = ft.AlertDialog(modal=True, title=ft.Text("Full MineHoster Reset"), content=ft.Column([ft.Text("This deletes every managed server, private JRE, cache, schedules and MineHoster configuration."), ft.Text("Your MineHoster executable is not deleted."), confirm], tight=True), actions=[ft.TextButton("Cancel", on_click=lambda ev: self._close_dialog(dialog)), ft.ElevatedButton("Reset Everything", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=lambda ev: self._run_reset(dialog, confirm))])
        self.app.page.dialog = dialog; dialog.open = True; self.app.page.update()

    def _close_dialog(self, dialog):
        dialog.open = False; self.app.page.update()

    def _run_reset(self, dialog, confirm):
        if (confirm.value or '').strip().upper() != 'RESET':
            self.status.value = 'Type RESET exactly to confirm.'; self.status.color = COLORS['danger']; self._safe_update(); return
        if self.resetting: return
        self.resetting = True; dialog.open = False; self.status.value = 'Stopping servers and deleting MineHoster data...'; self.status.color = COLORS['subtext']; self._safe_update()
        def worker():
            try:
                self.scheduler.stop()
                for server in list(self.sm.get_servers()): self.sm.delete_server(server.name)
                self.sm.servers.clear(); self.sm._save(); shutil.rmtree(DATA_ROOT, ignore_errors=True)
            finally:
                try: self.app.page.window.close()
                except Exception:
                    try: self.app.page.window.destroy()
                    except Exception: pass
        threading.Thread(target=worker, daemon=True).start()

    def _safe_update(self):
        try: self.app.page.update()
        except Exception: pass
