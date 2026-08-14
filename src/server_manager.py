import json
import os
import subprocess
import threading
import shutil
import urllib.request
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Callable, Optional

SERVERS_FILE = Path.home() / ".minehoster" / "servers.json"
SERVERS_DIR = Path.home() / ".minehoster" / "servers"

BDS_DOWNLOAD = "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.51.02.zip"


@dataclass
class ServerConfig:
    name: str
    version: str
    loader: str  # vanilla, paper, fabric, forge, bedrock
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


def _java_launch_cmd(folder: Path, ram_mb: int) -> list[str]:
    """
    Optimized Java launch flags:
    - -Xms sets starting heap low (256M) so it doesn't grab max RAM immediately
    - -Xmx caps max heap at user setting
    - G1GC flags tune garbage collection for MC servers (less stuttering, less RAM waste)
    - -XX:+UseStringDeduplication saves memory on duplicate strings
    - server.jar nogui skips the GUI which uses extra memory
    """
    return [
        "java",
        "-Xms256M",
        f"-Xmx{ram_mb}M",
        "-XX:+UseG1GC",
        "-XX:+ParallelRefProcEnabled",
        "-XX:MaxGCPauseMillis=200",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:+AlwaysPreTouch",
        "-XX:G1HeapWastePercent=5",
        "-XX:G1MixedGCCountTarget=4",
        "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:SurvivorRatio=32",
        "-XX:+PerfDisableSharedMem",
        "-XX:MaxTenuringThreshold=1",
        "-XX:+UseStringDeduplication",
        "-Dusing.aikars.flags=https://mcflags.emc.gs",
        "-jar", "server.jar", "nogui",
    ]


class ServerManager:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        SERVERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SERVERS_DIR.mkdir(parents=True, exist_ok=True)
        self.servers: dict[str, ServerConfig] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.console_callbacks: dict[str, list[Callable]] = {}
        self._load()

    def _load(self):
        if SERVERS_FILE.exists():
            try:
                data = json.loads(SERVERS_FILE.read_text())
                for name, cfg in data.items():
                    cfg.pop("running", None)
                    self.servers[name] = ServerConfig(**cfg)
            except Exception:
                pass

    def _save(self):
        data = {}
        for name, cfg in self.servers.items():
            d = asdict(cfg)
            d.pop("running", None)
            data[name] = d
        SERVERS_FILE.write_text(json.dumps(data, indent=2))

    def get_servers(self) -> list[ServerConfig]:
        return list(self.servers.values())

    def create_server(self, config: ServerConfig, download_url: str, progress_cb: Callable = None) -> bool:
        folder = Path(config.folder) if config.folder else SERVERS_DIR / config.name
        folder.mkdir(parents=True, exist_ok=True)
        config.folder = str(folder)

        if config.loader == "bedrock":
            return self._create_bedrock(config, folder, progress_cb)

        jar_path = folder / "server.jar"
        if not jar_path.exists():
            if progress_cb:
                progress_cb("downloading", f"Downloading {config.loader} {config.version}...")
            try:
                def reporthook(count, block_size, total_size):
                    if total_size > 0 and progress_cb:
                        pct = int(count * block_size * 100 / total_size)
                        progress_cb("progress", f"Downloading... {min(pct, 100)}%")
                urllib.request.urlretrieve(download_url, jar_path, reporthook)
            except Exception as e:
                if progress_cb:
                    progress_cb("error", f"Download failed: {e}")
                return False

        # Accept EULA
        (folder / "eula.txt").write_text("eula=true\n")
        self._write_properties(folder, config)

        if progress_cb:
            progress_cb("done", "Server created successfully!")

        self.servers[config.name] = config
        self._save()
        return True

    def _create_bedrock(self, config: ServerConfig, folder: Path, progress_cb: Callable = None) -> bool:
        import zipfile

        zip_path = folder / "bds.zip"
        if not (folder / "bedrock_server.exe").exists():
            if progress_cb:
                progress_cb("downloading", "Downloading Bedrock Dedicated Server...")
            try:
                def reporthook(count, block_size, total_size):
                    if total_size > 0 and progress_cb:
                        pct = int(count * block_size * 100 / total_size)
                        progress_cb("progress", f"Downloading BDS... {min(pct, 100)}%")
                urllib.request.urlretrieve(BDS_DOWNLOAD, zip_path, reporthook)
                if progress_cb:
                    progress_cb("progress", "Extracting...")
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(folder)
                zip_path.unlink(missing_ok=True)
            except Exception as e:
                if progress_cb:
                    progress_cb("error", f"Download failed: {e}")
                return False

        # Write server.properties for Bedrock
        props = [
            f"server-name={config.motd}\n",
            f"gamemode={config.gamemode}\n",
            f"difficulty={config.difficulty}\n",
            "allow-cheats=false\n",
            f"max-players={config.max_players}\n",
            f"online-mode={str(config.online_mode).lower()}\n",
            f"white-list={str(config.whitelist).lower()}\n",
            f"server-port={config.port}\n",
            f"server-portv6={config.port + 1}\n",
            "view-distance=10\n",
            "tick-distance=4\n",
            "level-name=Bedrock level\n",
            "level-seed=\n",
            "default-player-permission-level=member\n",
            "texturepack-required=false\n",
        ]
        (folder / "server.properties").write_text("".join(props))

        if progress_cb:
            progress_cb("done", "Bedrock server created!")
        self.servers[config.name] = config
        self._save()
        return True

    def _write_properties(self, folder: Path, cfg: ServerConfig):
        props = {
            "server-port": cfg.port,
            "online-mode": str(cfg.online_mode).lower(),
            "enable-command-block": str(cfg.command_blocks).lower(),
            "max-players": cfg.max_players,
            "difficulty": cfg.difficulty,
            "gamemode": cfg.gamemode,
            "pvp": str(cfg.pvp).lower(),
            "white-list": str(cfg.whitelist).lower(),
            "motd": cfg.motd,
            "level-name": "world",
            "spawn-protection": "16",
            "allow-nether": "true",
            "allow-flight": "false",
            "spawn-monsters": "true",
            "generate-structures": "true",
            "view-distance": "10",
        }
        lines = ["#Minecraft server properties\n"]
        for k, v in props.items():
            lines.append(f"{k}={v}\n")
        (folder / "server.properties").write_text("".join(lines))

    def update_properties(self, name: str, props: dict):
        cfg = self.servers.get(name)
        if not cfg:
            return
        folder = Path(cfg.folder)
        prop_file = folder / "server.properties"
        existing = {}
        if prop_file.exists():
            for line in prop_file.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()
        existing.update(props)
        lines = ["#Minecraft server properties\n"]
        for k, v in existing.items():
            lines.append(f"{k}={v}\n")
        prop_file.write_text("".join(lines))

    def get_properties(self, name: str) -> dict:
        cfg = self.servers.get(name)
        if not cfg:
            return {}
        prop_file = Path(cfg.folder) / "server.properties"
        result = {}
        if prop_file.exists():
            for line in prop_file.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip()
        return result

    def start_server(self, name: str):
        cfg = self.servers.get(name)
        if not cfg or name in self.processes:
            return
        folder = Path(cfg.folder)

        if cfg.loader == "bedrock":
            exe = folder / "bedrock_server.exe"
            if not exe.exists():
                for cb in self.console_callbacks.get(name, []):
                    cb("[ERROR] bedrock_server.exe not found. Please recreate the server.")
                return
            cmd = [str(exe)]
            proc = subprocess.Popen(
                cmd, cwd=folder,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, text=True, bufsize=1,
                env={"LD_LIBRARY_PATH": ".", **os.environ},
            )
        else:
            jar = folder / "server.jar"
            if not jar.exists():
                for cb in self.console_callbacks.get(name, []):
                    cb("[ERROR] server.jar not found. Please recreate the server.")
                return
            cmd = _java_launch_cmd(folder, cfg.ram_mb)
            proc = subprocess.Popen(
                cmd, cwd=folder,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, text=True, bufsize=1,
            )

        self.processes[name] = proc
        cfg.running = True
        threading.Thread(target=self._read_output, args=(name, proc), daemon=True).start()

    def _read_output(self, name: str, proc: subprocess.Popen):
        for line in proc.stdout:
            for cb in self.console_callbacks.get(name, []):
                cb(line.rstrip())
        if name in self.servers:
            self.servers[name].running = False
        self.processes.pop(name, None)
        # Fire callbacks with stopped message
        for cb in self.console_callbacks.get(name, []):
            cb("[MineHoster] Server stopped.")

    def stop_server(self, name: str):
        proc = self.processes.get(name)
        if proc:
            try:
                proc.stdin.write("stop\n")
                proc.stdin.flush()
            except Exception:
                proc.terminate()

    def restart_server(self, name: str):
        self.stop_server(name)
        import time
        time.sleep(3)
        self.start_server(name)

    def send_command(self, name: str, cmd: str):
        proc = self.processes.get(name)
        if proc:
            try:
                proc.stdin.write(cmd + "\n")
                proc.stdin.flush()
            except Exception:
                pass

    def is_running(self, name: str) -> bool:
        return name in self.processes

    def delete_server(self, name: str):
        self.stop_server(name)
        cfg = self.servers.pop(name, None)
        if cfg and cfg.folder:
            shutil.rmtree(cfg.folder, ignore_errors=True)
        self._save()

    def register_console_callback(self, name: str, cb: Callable):
        self.console_callbacks.setdefault(name, []).append(cb)

    def unregister_console_callbacks(self, name: str):
        self.console_callbacks.pop(name, None)

    def get_whitelist(self, name: str) -> list:
        cfg = self.servers.get(name)
        if not cfg:
            return []
        f = Path(cfg.folder) / "whitelist.json"
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                pass
        return []

    def add_whitelist(self, name: str, player: str):
        wl = self.get_whitelist(name)
        if not any(p.get("name") == player for p in wl):
            wl.append({"name": player, "uuid": ""})
        cfg = self.servers.get(name)
        if cfg:
            (Path(cfg.folder) / "whitelist.json").write_text(json.dumps(wl, indent=2))

    def remove_whitelist(self, name: str, player: str):
        wl = [p for p in self.get_whitelist(name) if p.get("name") != player]
        cfg = self.servers.get(name)
        if cfg:
            (Path(cfg.folder) / "whitelist.json").write_text(json.dumps(wl, indent=2))

    def get_ops(self, name: str) -> list:
        cfg = self.servers.get(name)
        if not cfg:
            return []
        f = Path(cfg.folder) / "ops.json"
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                pass
        return []

    def add_op(self, name: str, player: str):
        ops = self.get_ops(name)
        if not any(p.get("name") == player for p in ops):
            ops.append({"name": player, "uuid": "", "level": 4, "bypassesPlayerLimit": False})
        cfg = self.servers.get(name)
        if cfg:
            (Path(cfg.folder) / "ops.json").write_text(json.dumps(ops, indent=2))

    def remove_op(self, name: str, player: str):
        ops = [p for p in self.get_ops(name) if p.get("name") != player]
        cfg = self.servers.get(name)
        if cfg:
            (Path(cfg.folder) / "ops.json").write_text(json.dumps(ops, indent=2))

    def get_banned_players(self, name: str) -> list:
        cfg = self.servers.get(name)
        if not cfg:
            return []
        f = Path(cfg.folder) / "banned-players.json"
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                pass
        return []

    def ban_player(self, name: str, player: str):
        banned = self.get_banned_players(name)
        if not any(p.get("name") == player for p in banned):
            banned.append({"name": player, "uuid": "", "reason": "Banned by operator"})
        cfg = self.servers.get(name)
        if cfg:
            (Path(cfg.folder) / "banned-players.json").write_text(json.dumps(banned, indent=2))

    def unban_player(self, name: str, player: str):
        banned = [p for p in self.get_banned_players(name) if p.get("name") != player]
        cfg = self.servers.get(name)
        if cfg:
            (Path(cfg.folder) / "banned-players.json").write_text(json.dumps(banned, indent=2))

    def get_plugins_dir(self, name: str) -> Optional[Path]:
        cfg = self.servers.get(name)
        if not cfg:
            return None
        folder = Path(cfg.folder)
        return folder / "mods" if cfg.loader in ("fabric", "forge") else folder / "plugins"

    def list_plugins(self, name: str) -> list:
        d = self.get_plugins_dir(name)
        if not d or not d.exists():
            return []
        return [f.name for f in sorted(d.iterdir()) if f.suffix == ".jar"]

    def add_plugin(self, name: str, jar_path: str):
        d = self.get_plugins_dir(name)
        if not d:
            return
        d.mkdir(exist_ok=True)
        shutil.copy2(jar_path, d / Path(jar_path).name)

    def remove_plugin(self, name: str, plugin_name: str):
        d = self.get_plugins_dir(name)
        if not d:
            return
        target = d / plugin_name
        if target.exists():
            target.unlink()

    def list_files(self, name: str, subpath: str = "") -> list:
        cfg = self.servers.get(name)
        if not cfg:
            return []
        base = Path(cfg.folder) / subpath
        if not base.exists():
            return []
        items = []
        for f in sorted(base.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            items.append({
                "name": f.name,
                "is_dir": f.is_dir(),
                "size": f.stat().st_size if f.is_file() else 0,
                "path": str(f.relative_to(Path(cfg.folder))),
            })
        return items

    def read_file(self, name: str, rel_path: str) -> str:
        cfg = self.servers.get(name)
        if not cfg:
            return ""
        f = Path(cfg.folder) / rel_path
        try:
            return f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    def write_file(self, name: str, rel_path: str, content: str):
        cfg = self.servers.get(name)
        if not cfg:
            return
        f = Path(cfg.folder) / rel_path
        f.write_text(content, encoding="utf-8")

    def delete_file(self, name: str, rel_path: str):
        cfg = self.servers.get(name)
        if not cfg:
            return
        f = Path(cfg.folder) / rel_path
        if f.is_dir():
            shutil.rmtree(f)
        elif f.exists():
            f.unlink()
