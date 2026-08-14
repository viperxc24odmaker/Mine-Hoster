import shutil
import threading
from pathlib import Path
import flet as ft
from src.server_manager import ServerManager, SERVERS_FILE, SERVERS_DIR
from src.java_runtime import RUNTIMES_DIR
from src.theme import COLORS

DATA_ROOT = SERVERS_FILE.parent

class HostingSettingsView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.status = ft.Text("", color=COLORS["subtext"], size=12)
        self.resetting = False

    def _card(self, title, subtitle, controls):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=COLORS["text"]),
                ft.Text(subtitle, color=COLORS["subtext"], size=12),
                ft.Container(height=8),
                *controls,
            ], spacing=8),
            bgcolor=COLORS["card"], border_radius=12, padding=20,
            border=ft.border.all(1, COLORS["border"]),
        )

    def build(self):
        servers = self.sm.get_servers()
        server_count = len(servers)
        return ft.Container(
            content=ft.Column([
                ft.Text("Hosting Settings", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                ft.Text("Manage MineHoster's local hosting data and recovery tools.", color=COLORS["subtext"], size=13),
                ft.Container(height=16),
                self._card("MineHoster Hosting", "Core local hosting data used by your servers, JREs and cached metadata.", [
                    ft.Text(f"Data folder: {DATA_ROOT}", color=COLORS["muted"], size=11, selectable=True),
                    ft.Text(f"Managed servers: {server_count}", color=COLORS["subtext"], size=12),
                    ft.Text("Existing JREs and server files are reused automatically. Resetting removes them.", color=COLORS["subtext"], size=12),
                ]),
                ft.Container(height=14),
                self._card("Server Data", "Delete individual servers without affecting the rest of MineHoster.", [
                    ft.ElevatedButton("Open Server Dashboard", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=lambda e: self.app.navigate("dashboard")),
                ]),
                ft.Container(height=14),
                self._card("Full Reset", "Danger zone. This removes MineHoster's local hosting data, including all servers, private JREs and cached files. The application itself is not uninstalled.", [
                    ft.Text("This action cannot be undone.", color=COLORS["danger"], size=12, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton("FULL RESET MINEHOSTER", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=self._confirm_reset),
                    self.status,
                ]),
            ], scroll=ft.ScrollMode.AUTO), padding=32, expand=True,
        )

    def _confirm_reset(self, e):
        confirm = ft.TextField(label='Type RESET to confirm', width=300, autofocus=True)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Full MineHoster Reset"),
            content=ft.Column([
                ft.Text("This deletes every managed server, private JRE, cache and MineHoster configuration."),
                ft.Text("Your MineHoster executable is not deleted."),
                confirm,
            ], tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: self._close_dialog(dialog)),
                ft.ElevatedButton("Reset Everything", bgcolor=COLORS["danger"], color=COLORS["text"], on_click=lambda ev: self._run_reset(dialog, confirm)),
            ],
        )
        self.app.page.dialog = dialog
        dialog.open = True
        self.app.page.update()

    def _close_dialog(self, dialog):
        dialog.open = False
        self.app.page.update()

    def _run_reset(self, dialog, confirm):
        if (confirm.value or '').strip().upper() != 'RESET':
            self.status.value = 'Type RESET exactly to confirm.'
            self.status.color = COLORS['danger']
            self._safe_update()
            return
        if self.resetting:
            return
        self.resetting = True
        dialog.open = False
        self.status.value = 'Stopping servers and deleting MineHoster data...'
        self.status.color = COLORS['subtext']
        self._safe_update()

        def worker():
            try:
                for server in list(self.sm.get_servers()):
                    self.sm.delete_server(server.name)
                self.sm.servers.clear()
                try:
                    self.sm._save()
                except Exception:
                    pass
                shutil.rmtree(DATA_ROOT, ignore_errors=True)
                # Do not delete the executable/install directory; only MineHoster's managed data is reset.
            finally:
                try:
                    self.app.page.window.close()
                except Exception:
                    try:
                        self.app.page.window.destroy()
                    except Exception:
                        pass
        threading.Thread(target=worker, daemon=True).start()

    def _safe_update(self):
        try:
            self.status.update()
            self.app.page.update()
        except Exception:
            pass
