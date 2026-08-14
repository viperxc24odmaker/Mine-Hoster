import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS


class FileManagerView:
    def __init__(self, app):
        self.app = app
        self.sm = ServerManager.get()
        self.selected = app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None)
        self.current_path = ""
        self.file_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=2)
        self.editor_field = ft.TextField(
            multiline=True, expand=True, min_lines=20,
            border_color=COLORS["border"], focused_border_color=COLORS["accent"],
            color=COLORS["text"], bgcolor=COLORS["surface2"],
            text_style=ft.TextStyle(font_family="Courier New", size=13),
        )
        self.editing_path = ""
        self.breadcrumb = ft.Text("", color=COLORS["subtext"], size=12)
        self.editor_container = ft.Ref[ft.Container]()
        self.file_container = ft.Ref[ft.Container]()

    def build(self):
        servers = self.sm.get_servers()
        if not servers:
            return ft.Container(
                content=ft.Text("No servers found.", color=COLORS["subtext"]),
                padding=32,
            )

        server_dd = ft.Dropdown(
            value=self.selected,
            options=[ft.dropdown.Option(s.name) for s in servers],
            on_change=self._on_server_change,
            border_color=COLORS["border"],
            focused_border_color=COLORS["accent"],
            color=COLORS["text"],
            bgcolor=COLORS["surface2"],
            width=200,
        )

        if self.selected:
            self._refresh_files()

        self.editor_container_ctrl = ft.Container(
            ref=self.editor_container,
            visible=False,
            content=ft.Column([
                ft.Row([
                    ft.Text("Editing: ", color=COLORS["subtext"], size=12),
                    ft.Text(self.editing_path or "", color=COLORS["text"], size=12),
                    ft.Row([
                        ft.ElevatedButton("Save", bgcolor=COLORS["accent2"], color=COLORS["text"], on_click=self._save_file),
                        ft.ElevatedButton("Close", bgcolor=COLORS["surface2"], color=COLORS["text"], on_click=self._close_editor),
                    ], spacing=8),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.editor_field,
            ], expand=True, spacing=8),
            expand=True,
        )

        self.file_container_ctrl = ft.Container(
            ref=self.file_container,
            content=self.file_list_col,
            expand=True,
        )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("File Manager", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    server_dd,
                ], spacing=16),
                ft.Container(height=8),
                ft.Row([
                    ft.IconButton(
                        icon=ft.icons.ARROW_BACK,
                        icon_color=COLORS["subtext"],
                        tooltip="Go up",
                        on_click=self._go_up,
                    ),
                    self.breadcrumb,
                ], spacing=8),
                ft.Divider(color=COLORS["border"]),
                self.file_container_ctrl,
                self.editor_container_ctrl,
            ], expand=True),
            padding=32,
            expand=True,
        )

    def _refresh_files(self):
        if not self.selected:
            return
        files = self.sm.list_files(self.selected, self.current_path)
        self.breadcrumb.value = f"/{self.current_path}" if self.current_path else "/"
        self.file_list_col.controls.clear()
        for f in files:
            self.file_list_col.controls.append(self._file_row(f))
        try:
            self.file_list_col.update()
            self.breadcrumb.update()
        except Exception:
            pass

    def _file_row(self, f: dict):
        icon = "📁" if f["is_dir"] else "📄"
        size_str = "" if f["is_dir"] else self._fmt_size(f["size"])

        def open_item(e, item=f):
            if item["is_dir"]:
                self.current_path = item["path"]
                self._refresh_files()
            else:
                self._open_editor(item["path"])

        def delete_item(e, item=f):
            self.sm.delete_file(self.selected, item["path"])
            self._refresh_files()

        return ft.Container(
            content=ft.Row([
                ft.Text(icon, size=16),
                ft.Text(f["name"], color=COLORS["text"], size=13, expand=True),
                ft.Text(size_str, color=COLORS["subtext"], size=11),
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    icon_color=COLORS["danger"],
                    icon_size=16,
                    tooltip="Delete",
                    on_click=delete_item,
                ),
            ], spacing=8),
            on_click=open_item,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=6,
            ink=True,
        )

    def _fmt_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size // 1024} KB"
        else:
            return f"{size // (1024*1024)} MB"

    def _open_editor(self, path: str):
        content = self.sm.read_file(self.selected, path)
        self.editor_field.value = content
        self.editing_path = path
        self.editor_container_ctrl.visible = True
        self.file_container_ctrl.visible = False
        try:
            self.editor_container_ctrl.update()
            self.file_container_ctrl.update()
            self.editor_field.update()
        except Exception:
            pass

    def _save_file(self, e):
        if self.editing_path and self.selected:
            self.sm.write_file(self.selected, self.editing_path, self.editor_field.value or "")
        self._close_editor(e)

    def _close_editor(self, e):
        self.editor_container_ctrl.visible = False
        self.file_container_ctrl.visible = True
        self.editing_path = ""
        try:
            self.editor_container_ctrl.update()
            self.file_container_ctrl.update()
        except Exception:
            pass

    def _go_up(self, e):
        if self.current_path:
            parts = self.current_path.replace("\\", "/").split("/")
            self.current_path = "/".join(parts[:-1])
            self._refresh_files()

    def _on_server_change(self, e):
        self.selected = e.control.value
        self.current_path = ""
        self._refresh_files()
