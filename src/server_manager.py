import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

from src.java_runtime import ensure_java

SERVERS_FILE = Path.home() / ".minehoster" / "servers.json"
SERVERS_DIR = Path.home() / ".minehoster" / "servers"
BDS_DOWNLOAD = "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.51.02.zip"
USER_AGENT = "MineHoster/2.0 (https://github.com/viperxc24odmaker/Mine-Hoster)"

@dataclass
class ServerConfig:
    name: str
    version: str
    loader: str
    port: int = 25565
    ram_mb: int = 2048
    folder: str = ""
    online_mode: bool = True
    command_blocks: bool = False
    max_players: int = 20
    difficulty: str = "normal"
    gamemode: str = "survival"
    pvp: bool = True
    whitelist: bool = False
    motd: str = "A MineHoster Server"
    running: bool = False


def _java_required(version: str) -> int:
    parts = version.split(".")
    try:
        major = int(parts[0]); minor = int(parts[1]) if major == 1 and len(parts) > 1 else major
    except (ValueError, IndexError): return 21
    if major >= 26: return 25
    if minor >= 20: return 21
    if minor >= 17: return 17
    if minor == 16: return 16
    return 11

class ServerManager:
    _instance = None
    @classmethod
    def get(cls):
        if cls._instance is None: cls._instance = cls()
        return cls._instance

    def __init__(self):
        SERVERS_FILE.parent.mkdir(parents=True, exist_ok=True); SERVERS_DIR.mkdir(parents=True, exist_ok=True)
        self.servers: dict[str, ServerConfig] = {}; self.processes: dict[str, subprocess.Popen] = {}; self.console_callbacks: dict[str, list[Callable]] = {}; self._load()

    def _load(self):
        if not SERVERS_FILE.exists(): return
        try:
            data = json.loads(SERVERS_FILE.read_text(encoding="utf-8"))
            for name, raw in data.items():
                if isinstance(raw, dict): raw = dict(raw); raw.pop("running", None); self.servers[name] = ServerConfig(**raw)
        except (OSError, ValueError, TypeError): self.servers = {}

    def _save(self):
        data = {}
        for name, cfg in self.servers.items():
            raw = asdict(cfg); raw.pop("running", None); data[name] = raw
        temp = SERVERS_FILE.with_suffix(".tmp"); temp.write_text(json.dumps(data, indent=2), encoding="utf-8"); temp.replace(SERVERS_FILE)

    def get_servers(self): return list(self.servers.values())
    def _emit(self, name, line):
        for callback in list(self.console_callbacks.get(name, [])):
            try: callback(line)
            except Exception: pass

    def _download(self, url, target, progress_cb=None, label="Downloading"):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as response, target.open("wb") as out:
            total = int(response.headers.get("Content-Length", 0)); done = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                out.write(chunk); done += len(chunk)
                if progress_cb:
                    percent = min(100, int(done * 100 / total)) if total else None
                    progress_cb("progress", f"{label}... {percent}%" if percent is not None else f"{label}...", percent)

    def create_server(self, config, download_url, progress_cb=None):
        folder = (Path(config.folder).expanduser() if config.folder else SERVERS_DIR / config.name).resolve(); folder.mkdir(parents=True, exist_ok=True); config.folder = str(folder)
        try:
            if config.loader == "bedrock": self._create_bedrock(config, folder, download_url, progress_cb)
            elif config.loader == "forge": self._prepare_forge(config, folder, download_url, progress_cb)
            else:
                jar = folder / "server.jar"
                if not jar.exists():
                    if not download_url: raise RuntimeError("No server download URL was returned.")
                    if progress_cb: progress_cb("downloading", f"Downloading {config.loader.title()} {config.version} server.jar...", 0)
                    part = folder / "server.jar.part"
                    try:
                        self._download(download_url, part, progress_cb, f"Downloading {config.loader.title()} {config.version} server.jar")
                        if part.stat().st_size < 1024: raise RuntimeError("Downloaded server file is unexpectedly small.")
                        part.replace(jar)
                    finally: part.unlink(missing_ok=True)
            (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8"); self._write_properties(folder, config); self.servers[config.name] = config; self._save()
            if progress_cb: progress_cb("done", "Server created successfully!", 100)
            return True
        except Exception as exc:
            if progress_cb: progress_cb("error", f"Setup failed: {exc}", 0)
            return False

    def _create_bedrock(self, config, folder, url, progress_cb):
        import zipfile
        exe = folder / "bedrock_server.exe"
        if not exe.exists():
            if progress_cb: progress_cb("downloading", "Downloading Bedrock Dedicated Server...", 0)
            part = folder / "bds.zip.part"
            try:
                self._download(url or BDS_DOWNLOAD, part, progress_cb, "Downloading Bedrock Dedicated Server")
                if progress_cb: progress_cb("installing", "Extracting Bedrock server files...", 100)
                with zipfile.ZipFile(part) as archive: archive.extractall(folder)
            finally: part.unlink(missing_ok=True)
        if not exe.exists(): raise RuntimeError("bedrock_server.exe was not found after extraction.")
        props = [f"server-name={config.motd}", f"gamemode={config.gamemode}", f"difficulty={config.difficulty}", "allow-cheats=false", f"max-players={config.max_players}", f"online-mode={str(config.online_mode).lower()}", f"white-list={str(config.whitelist).lower()}", f"server-port={config.port}", f"server-portv6={config.port + 1}", "view-distance=10", "tick-distance=4", "level-name=Bedrock level", "level-seed=", "default-player-permission-level=member", "texturepack-required=false"]
        (folder / "server.properties").write_text("\n".join(props) + "\n", encoding="utf-8")

    def _prepare_forge(self, config, folder, url, progress_cb):
        script = folder / ("run.bat" if os.name == "nt" else "run.sh")
        if script.exists(): return
        if not url: raise RuntimeError("No Forge installer URL was returned.")
        java = ensure_java(_java_required(config.version), progress_cb)
        installer = folder / "forge-installer.jar"
        if not installer.exists():
            if progress_cb: progress_cb("downloading", f"Downloading Forge {config.version} installer...", 0)
            part = folder / "forge-installer.jar.part"
            try:
                self._download(url, part, progress_cb, f"Downloading Forge {config.version} installer")
                if part.stat().st_size < 1024: raise RuntimeError("Downloaded Forge installer is unexpectedly small.")
                part.replace(installer)
            finally: part.unlink(missing_ok=True)
        if progress_cb: progress_cb("installing", "Installing Forge server files...", 100)
        result = subprocess.run([java, "-jar", installer.name, "--installServer"], cwd=str(folder), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
        installer.unlink(missing_ok=True)
        if result.returncode != 0: raise RuntimeError(f"Forge installer failed (exit {result.returncode}).\n{chr(10).join((result.stdout or '').splitlines()[-8:])}")
        if not script.exists(): raise RuntimeError("Forge installed, but its run script was not generated.")
