from __future__ import annotations
import json
from pathlib import Path
import flet as ft
from src.server_manager import ServerManager
from src.theme import COLORS
SETTINGS_FILE = Path.home() / ".minehoster" / "settings.json"
DEFAULTS = {"theme": "dark", "accent": "gray", "confirm_destructive": True, "auto_start_playit": False, "default_server_folder": ""}
def load_settings():
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
        return {**DEFAULTS, **(data if isinstance(data, dict) else {})}
    except Exception: return dict(DEFAULTS)
def save_settings(data):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True); tmp = SETTINGS_FILE.with_suffix(".tmp"); tmp.write_text(json.dumps(data, indent=2), encoding="utf-8"); tmp.replace(SETTINGS_FILE)
class SettingsViewV2:
    def __init__(self, app):
        self.app=app; self.sm=ServerManager.get(); self.selected=app.selected_server or (self.sm.get_servers()[0].name if self.sm.get_servers() else None); self.data=load_settings(); style=dict(border_color=COLORS["border"], focused_border_color=COLORS["accent"], color=COLORS["text"], bgcolor=COLORS["surface2"])
        self.status=ft.Text("Changes are local to this PC.", color=COLORS["subtext"], size=12); self.folder=ft.TextField(label="Default server folder", value=self.data.get("default_server_folder",""), expand=True, **style); self.accent=ft.Dropdown(label="Accent", value=self.data.get("accent","gray"), options=[ft.dropdown.Option(x) for x in ["gray","blue","purple","green"]], width=180); self.theme=ft.Dropdown(label="Theme", value=self.data.get("theme","dark"), options=[ft.dropdown.Option(x) for x in ["dark","light"]], width=180); self.confirm=ft.Switch(label="Confirm destructive actions", value=bool(self.data.get("confirm_destructive",True))); self.auto_playit=ft.Switch(label="Auto-connect Playit when a server starts", value=bool(self.data.get("auto_start_playit",False))); self.prop_col=ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO); self.fields={}
    def _card(self,title,subtitle,controls): return ft.Container(content=ft.Column([ft.Text(title,size=16,weight=ft.FontWeight.BOLD,color=COLORS["text"]),ft.Text(subtitle,size=12,color=COLORS["subtext"]),ft.Container(height=6),*controls]),bgcolor=COLORS["card"],border_radius=14,padding=20,border=ft.border.all(1,COLORS["border"]))
    def build(self):
        servers=self.sm.get_servers(); dd=ft.Dropdown(value=self.selected,options=[ft.dropdown.Option(s.name) for s in servers],on_change=self._server_change,width=220) if servers else ft.Text("No servers yet.",color=COLORS["subtext"])
        if self.selected:self._load_props()
        return ft.Container(content=ft.Column([ft.Text("Settings",size=26,weight=ft.FontWeight.BOLD,color=COLORS["text"]),ft.Text("Every control here is live-editable and persisted safely.",size=13,color=COLORS["subtext"]),ft.Container(height=10),self._card("Appearance","Default is the gray/dark MineHoster look; users can change it without touching code.",[ft.Row([self.theme,self.accent],wrap=True),ft.ElevatedButton("Save App Settings",on_click=self._save_app)]),ft.Container(height=14),self._card("Hosting defaults","These values affect new servers and can be overridden per server.",[ft.Row([self.folder,ft.ElevatedButton("Use MineHoster Default",on_click=self._clear_folder)],expand=True),self.confirm,self.auto_playit]),ft.Container(height=14),self._card("Server properties","Edit the real server.properties file. Changes persist immediately when saved.",[dd,self.prop_col,ft.Row([ft.ElevatedButton("Save Server Properties",on_click=self._save_props),self.status],wrap=True)])],scroll=ft.ScrollMode.AUTO),padding=28,expand=True)
    def _load_props(self):
        self.prop_col.controls.clear(); self.fields.clear(); props=self.sm.get_properties(self.selected) if self.selected else {}
        for key,value in props.items():
            field=ft.TextField(label=key,value=str(value),expand=True,border_color=COLORS["border"],focused_border_color=COLORS["accent"],color=COLORS["text"],bgcolor=COLORS["surface2"]); self.fields[key]=field; self.prop_col.controls.append(field)
    def _save_props(self,e):
        if not self.selected:return
        self.sm.update_properties(self.selected,{k:f.value for k,f in self.fields.items()}); self.status.value="✓ Server settings saved."; self.status.color=COLORS["accent2"]; self._safe()
    def _save_app(self,e):
        self.data.update({"theme":self.theme.value,"accent":self.accent.value,"confirm_destructive":self.confirm.value,"auto_start_playit":self.auto_playit.value,"default_server_folder":(self.folder.value or "").strip()}); save_settings(self.data); self.status.value="✓ App settings saved. Restart MineHoster to apply global appearance."; self.status.color=COLORS["accent2"]; self._safe()
    def _clear_folder(self,e):self.folder.value="";self._safe()
    def _server_change(self,e):self.selected=e.control.value;self._load_props();self._safe()
    def _safe(self):
        try:self.app.page.update()
        except Exception:pass
