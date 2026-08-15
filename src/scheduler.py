from __future__ import annotations

import json
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.server_manager import ServerManager, SERVERS_FILE

SCHEDULE_FILE = SERVERS_FILE.parent / "schedules.json"


class MineHosterScheduler:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.sm = ServerManager.get()
        self.jobs = self._load()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_run: dict[str, str] = {}

    def _load(self):
        try:
            data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self):
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SCHEDULE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.jobs, indent=2), encoding="utf-8")
        tmp.replace(SCHEDULE_FILE)

    def set_job(self, server: str, kind: str, enabled: bool, time_text: str, keep: int = 7):
        if server not in self.jobs:
            self.jobs[server] = {}
        self.jobs[server][kind] = {"enabled": bool(enabled), "time": time_text, "keep": max(1, int(keep))}
        self.save()

    def get_job(self, server: str, kind: str):
        return (self.jobs.get(server) or {}).get(kind, {"enabled": False, "time": "03:00", "keep": 7})

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MineHoster-Scheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(20):
            now = datetime.now()
            stamp = now.strftime("%Y-%m-%d")
            clock = now.strftime("%H:%M")
            for server, jobs in list(self.jobs.items()):
                for kind, job in list((jobs or {}).items()):
                    if not isinstance(job, dict) or not job.get("enabled") or job.get("time") != clock:
                        continue
                    key = f"{stamp}:{server}:{kind}"
                    if self._last_run.get(f"{server}:{kind}") == key:
                        continue
                    self._last_run[f"{server}:{kind}"] = key
                    try:
                        if kind == "backup":
                            self.create_backup(server, int(job.get("keep", 7)))
                        elif kind == "restart":
                            self.sm.restart_server(server)
                    except Exception:
                        # Scheduler must never be able to crash the app thread.
                        pass

    def create_backup(self, server: str, keep: int = 7):
        cfg = self.sm.servers.get(server)
        if not cfg:
            return None
        source = Path(cfg.folder)
        if not source.exists():
            return None
        backup_dir = source / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        target = backup_dir / f"{server}_{stamp}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if not path.is_file() or backup_dir in path.parents:
                    continue
                archive.write(path, path.relative_to(source))
        backups = sorted((p for p in backup_dir.glob("*.zip") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[max(1, keep):]:
            old.unlink(missing_ok=True)
        return target
