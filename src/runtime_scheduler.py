from __future__ import annotations

import json
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from src.server_manager import ServerManager

CONFIG = Path.home() / ".minehoster" / "hosting.json"
DEFAULT = {"backup_enabled": True, "backup_time": "03:00", "backup_keep": 7, "restart_enabled": False, "restart_time": "04:00", "restart_warn": 60}


def _load():
    try:
        raw = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
        return {**DEFAULT, **(raw if isinstance(raw, dict) else {})}
    except Exception:
        return dict(DEFAULT)


def _backup(sm, cfg):
    root = Path(cfg.folder); out_dir = Path.home() / ".minehoster" / "backups" / cfg.name; out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{cfg.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file(): z.write(p, p.relative_to(root))
    with zipfile.ZipFile(out, "r") as z:
        if z.testzip(): out.unlink(missing_ok=True); raise RuntimeError("backup verification failed")
    files = sorted(out_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[max(1, int(_load()["backup_keep"])):]: old.unlink(missing_ok=True)
    sm._emit(cfg.name, f"[MineHoster] Scheduled backup complete: {out.name}")


def start_scheduler():
    sm = ServerManager.get(); last = set()
    def loop():
        while True:
            now = datetime.now(); key = now.strftime("%Y-%m-%d %H:%M"); settings = _load()
            for cfg in sm.get_servers():
                if settings["backup_enabled"] and now.strftime("%H:%M") == settings["backup_time"] and (cfg.name, key, "b") not in last:
                    last.add((cfg.name, key, "b"))
                    threading.Thread(target=lambda c=cfg: _safe_backup(sm, c), daemon=True).start()
                if settings["restart_enabled"] and now.strftime("%H:%M") == settings["restart_time"] and (cfg.name, key, "r") not in last and sm.is_running(cfg.name):
                    last.add((cfg.name, key, "r")); threading.Thread(target=lambda c=cfg: _scheduled_restart(sm, c, int(settings["restart_warn"])), daemon=True).start()
            time.sleep(20)
    threading.Thread(target=loop, daemon=True, name="MineHoster-Scheduler").start()


def _safe_backup(sm, cfg):
    try: _backup(sm, cfg)
    except Exception as exc: sm._emit(cfg.name, f"[ERROR] Scheduled backup failed: {exc}")


def _scheduled_restart(sm, cfg, warning):
    try:
        if warning > 0:
            sm.send_command(cfg.name, f"say MineHoster: scheduled restart in {warning} seconds")
            time.sleep(warning)
        if sm.is_running(cfg.name):
            sm._emit(cfg.name, "[MineHoster] Scheduled restart starting...")
            sm.restart_server(cfg.name)
    except Exception as exc: sm._emit(cfg.name, f"[ERROR] Scheduled restart failed: {exc}")
