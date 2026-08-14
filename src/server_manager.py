import json
import os
import shutil
import stat
import subprocess
import threading
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

from src.java_runtime import ensure_java

SERVERS_FILE = Path.home() / ".minehoster" / "servers.json"
SERVERS_DIR = Path.home() / ".minehoster" / "servers"
BDS_REDIRECT = "https://aka.ms/MinecraftBDS"
BDS_FALLBACK = "https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-1.21.51.02.zip"
USER_AGENT = "MineHoster/2.0 (https://github.com/viperxc24odmaker/Mine-Hoster)"


def _hidden_process_kwargs():
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


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
        major = int(parts[0])
        minor = int(parts[1]) if major == 1 and len(parts) > 1 else major
    except (ValueError, IndexError):
        return 21
    if major >= 26:
        return 25
    if minor >= 20:
        return 21
    if minor >= 17:
        return 17
    if minor == 16:
        return 16
    return 11


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path):
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"Unsafe archive entry rejected: {member.filename}") from exc
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member, "r") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)


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
        if not SERVERS_FILE.exists():
            return
        try:
            data = json.loads(SERVERS_FILE.read_text(encoding="utf-8"))
            for name, raw in data.items():
                if isinstance(raw, dict):
                    raw = dict(raw)
                    raw.pop("running", None)
                    self.servers[name] = ServerConfig(**raw)
        except (OSError, ValueError, TypeError):
            self.servers = {}

    def _save(self):
        data = {}
        for name, cfg in self.servers.items():
            raw = asdict(cfg)
            raw.pop("running", None)
            data[name] = raw
        temp = SERVERS_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(SERVERS_FILE)

    def get_servers(self):
        return list(self.servers.values())

    def _emit(self, name, line):
        for callback in list(self.console_callbacks.get(name, [])):
            try:
                callback(line)
            except Exception:
                pass

    def _download(self, url, target, progress_cb=None, label="Downloading", retries=3):
        last_error = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "*/*",
                        "Accept-Encoding": "identity",
                    },
                )
                with urllib.request.urlopen(req, timeout=120) as response, target.open("wb") as out:
                    total = int(response.headers.get("Content-Length", 0) or 0)
                    done = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        if progress_cb:
                            percent = min(100, int(done * 100 / total)) if total else None
                            progress_cb(
                                "progress",
                                f"{label}... {percent}%" if percent is not None else f"{label}... {done // (1024 * 1024)} MB",
                                percent,
                            )
                if target.stat().st_size < 1024:
                    raise RuntimeError("Downloaded file is unexpectedly small.")
                return
            except Exception as exc:
                last_error = exc
                target.unlink(missing_ok=True)
                if attempt + 1 < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Download failed after {retries} attempts: {last_error}")

    def create_server(self, config, download_url, progress_cb=None):
        folder = (Path(config.folder).expanduser() if config.folder else SERVERS_DIR / config.name).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        config.folder = str(folder)
        try:
            if config.loader == "bedrock":
                self._create_bedrock(config, folder, download_url, progress_cb)
            elif config.loader == "forge":
                self._prepare_forge(config, folder, download_url, progress_cb)
            else:
                jar = folder / "server.jar"
                if not jar.exists():
                    if not download_url:
                        raise RuntimeError("No server download URL was returned.")
                    if progress_cb:
                        progress_cb("downloading", f"Downloading {config.loader.title()} {config.version} server.jar...", 0)
                    part = folder / "server.jar.part"
                    try:
                        self._download(download_url, part, progress_cb, f"Downloading {config.loader.title()} {config.version} server.jar")
                        part.replace(jar)
                    finally:
                        part.unlink(missing_ok=True)
            (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            self._write_properties(folder, config)
            self.servers[config.name] = config
            self._save()
            if progress_cb:
                progress_cb("done", "Server created successfully!", 100)
            return True
        except Exception as exc:
            if progress_cb:
                progress_cb("error", f"Setup failed: {exc}", 0)
            return False

    def _resolve_bds_url(self, preferred=None):
        candidates = [preferred, BDS_REDIRECT, BDS_FALLBACK]
        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                req = urllib.request.Request(candidate, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    final_url = response.geturl()
                    if final_url.lower().endswith(".zip"):
                        return final_url
            except Exception:
                continue
        raise RuntimeError("Could not resolve an official Bedrock Dedicated Server download URL.")

    def _create_bedrock(self, config, folder, url, progress_cb):
        exe_name = "bedrock_server.exe" if os.name == "nt" else "bedrock_server"
        exe = folder / exe_name
        if not exe.exists():
            resolved_url = self._resolve_bds_url(url)
            if progress_cb:
                progress_cb("downloading", f"Downloading Bedrock Dedicated Server ({resolved_url.rsplit('/', 1)[-1]})...", 0)
            part = folder / "bds.zip.part"
            archive_path = folder / "bds.zip"
            try:
                self._download(resolved_url, part, progress_cb, "Downloading Bedrock Dedicated Server")
                part.replace(archive_path)
                if progress_cb:
                    progress_cb("installing", "Validating Bedrock archive...", 100)
                with zipfile.ZipFile(archive_path, "r") as archive:
                    bad = archive.testzip()
                    if bad:
                        raise RuntimeError(f"Bedrock archive is corrupt at {bad}.")
                    if not any(Path(i.filename).name == exe_name for i in archive.infolist()):
                        raise RuntimeError(f"Bedrock archive does not contain {exe_name}.")
                    if progress_cb:
                        progress_cb("installing", "Extracting Bedrock server files...", 100)
                    _safe_extract_zip(archive, folder)
            finally:
                part.unlink(missing_ok=True)
                archive_path.unlink(missing_ok=True)
        if not exe.exists():
            raise RuntimeError(f"{exe_name} was not found after extraction.")
        if os.name != "nt":
            exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        props = [
            f"server-name={str(config.motd).replace(';', ' ')}",
            f"gamemode={config.gamemode}",
            f"difficulty={config.difficulty}",
            "allow-cheats=false",
            f"max-players={config.max_players}",
            f"online-mode={str(config.online_mode).lower()}",
            f"allow-list={str(config.whitelist).lower()}",
            f"server-port={config.port}",
            f"server-portv6={config.port + 1}",
            "view-distance=10",
            "tick-distance=4",
            "level-name=Bedrock level",
            "level-seed=",
            "default-player-permission-level=member",
            "texturepack-required=false",
        ]
        (folder / "server.properties").write_text("\n".join(props) + "\n", encoding="utf-8")

    def _prepare_forge(self, config, folder, url, progress_cb):
        script = folder / ("run.bat" if os.name == "nt" else "run.sh")
        if script.exists():
            return
        if not url:
            raise RuntimeError("No Forge installer URL was returned.")
        java = ensure_java(_java_required(config.version), progress_cb)
        installer = folder / "forge-installer.jar"
        if not installer.exists():
            if progress_cb:
                progress_cb("downloading", f"Downloading Forge {config.version} installer...", 0)
            part = folder / "forge-installer.jar.part"
            try:
                self._download(url, part, progress_cb, f"Downloading Forge {config.version} installer")
                part.replace(installer)
            finally:
                part.unlink(missing_ok=True)
        if progress_cb:
            progress_cb("installing", "Installing Forge server files...", 100)
        result = subprocess.run(
            [java, "-jar", installer.name, "--installServer"],
            cwd=str(folder),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
            **_hidden_process_kwargs(),
        )
        installer.unlink(missing_ok=True)
        if result.returncode != 0:
            tail = "\n".join((result.stdout or "").splitlines()[-8:])
            raise RuntimeError(f"Forge installer failed (exit {result.returncode}).\n{tail}")
        if not script.exists():
            raise RuntimeError("Forge installed, but its run script was not generated.")
        (folder / "user_jvm_args.txt").write_text(
            f"-Xms{min(1024, max(512, config.ram_mb))}M\n-Xmx{max(512, config.ram_mb)}M\n",
            encoding="utf-8",
        )

    def _write_properties(self, folder, cfg):
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
            "spawn-protection": 16,
            "allow-nether": "true",
            "allow-flight": "false",
            "spawn-monsters": "true",
            "generate-structures": "true",
            "view-distance": 10,
        }
        (folder / "server.properties").write_text(
            "#Minecraft server properties\n" + "\n".join(f"{k}={v}" for k, v in props.items()) + "\n",
            encoding="utf-8",
        )

    def get_properties(self, name):
        cfg = self.servers.get(name)
        if not cfg:
            return {}
        result = {}
        path = Path(cfg.folder) / "server.properties"
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip()
        except OSError:
            pass
        return result

    def update_properties(self, name, props):
        cfg = self.servers.get(name)
        if not cfg:
            return False
        existing = self.get_properties(name)
        existing.update(props)
        (Path(cfg.folder) / "server.properties").write_text(
            "#Minecraft server properties\n" + "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
            encoding="utf-8",
        )
        return True

    def start_server(self, name):
        cfg = self.servers.get(name)
        if not cfg or self.is_running(name):
            return bool(cfg and self.is_running(name))
        folder = Path(cfg.folder)
        try:
            if cfg.loader == "bedrock":
                exe_name = "bedrock_server.exe" if os.name == "nt" else "bedrock_server"
                exe = folder / exe_name
                if not exe.exists():
                    raise RuntimeError(f"{exe_name} not found. Recreate the server.")
                cmd = [str(exe)]
            elif cfg.loader == "forge":
                script = folder / ("run.bat" if os.name == "nt" else "run.sh")
                if not script.exists():
                    raise RuntimeError("Forge run script not found. Recreate the server.")
                cmd = ["cmd", "/c", script.name] if os.name == "nt" else ["bash", script.name]
            else:
                jar = folder / "server.jar"
                if not jar.exists():
                    raise RuntimeError("server.jar not found. Recreate the server.")
                java = ensure_java(
                    _java_required(cfg.version),
                    lambda stage, msg, pct=None: self._emit(name, f"[MineHoster] {msg}"),
                )
                ram = max(512, int(cfg.ram_mb))
                cmd = [
                    java,
                    f"-Xms{min(1024, ram)}M",
                    f"-Xmx{ram}M",
                    "-XX:+UseG1GC",
                    "-XX:+ParallelRefProcEnabled",
                    "-XX:MaxGCPauseMillis=200",
                    "-XX:+DisableExplicitGC",
                    "-XX:+PerfDisableSharedMem",
                    "-jar",
                    "server.jar",
                    "--nogui",
                ]
            proc = subprocess.Popen(
                cmd,
                cwd=str(folder),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=os.environ.copy(),
                **_hidden_process_kwargs(),
            )
        except Exception as exc:
            cfg.running = False
            self._emit(name, f"[ERROR] Could not start server: {exc}")
            return False
        self.processes[name] = proc
        cfg.running = True
        self._emit(name, f"[MineHoster] Starting {cfg.loader.title()} {cfg.version}...")
        threading.Thread(target=self._read_output, args=(name, proc), daemon=True).start()
        return True

    def _read_output(self, name, proc):
        try:
            if proc.stdout:
                for line in proc.stdout:
                    self._emit(name, line.rstrip("\r\n"))
        except Exception as exc:
            self._emit(name, f"[ERROR] Console reader stopped: {exc}")
        finally:
            code = proc.poll()
            if code is None:
                try:
                    code = proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    code = -1
            self.processes.pop(name, None)
            if name in self.servers:
                self.servers[name].running = False
            self._emit(
                name,
                f"[MineHoster] Server process exited with code {code}."
                if code not in (0, None)
                else "[MineHoster] Server stopped.",
            )

    def stop_server(self, name):
        proc = self.processes.get(name)
        if not proc:
            return False
        try:
            if proc.stdin:
                proc.stdin.write("stop\n")
                proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

        def wait_and_kill():
            try:
                proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                self._emit(name, "[MineHoster] Stop timed out; terminating process...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

        threading.Thread(target=wait_and_kill, daemon=True).start()
        return True

    def restart_server(self, name):
        if self.is_running(name):
            self.stop_server(name)
            deadline = time.time() + 20
            while self.is_running(name) and time.time() < deadline:
                time.sleep(0.25)
        return self.start_server(name)

    def send_command(self, name, command):
        proc = self.processes.get(name)
        if not proc or proc.poll() is not None:
            self._emit(name, "[ERROR] Server is not running.")
            return False
        command = (command or "").strip().lstrip("/")
        if not command:
            return False
        try:
            if not proc.stdin:
                raise BrokenPipeError("stdin is unavailable")
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
            return True
        except (BrokenPipeError, OSError) as exc:
            self._emit(name, f"[ERROR] Failed to send command: {exc}")
            return False

    def is_running(self, name):
        proc = self.processes.get(name)
        return bool(proc and proc.poll() is None)

    def delete_server(self, name):
        self.stop_server(name)
        deadline = time.time() + 15
        while self.is_running(name) and time.time() < deadline:
            time.sleep(0.2)
        cfg = self.servers.pop(name, None)
        self.console_callbacks.pop(name, None)
        if cfg and cfg.folder:
            shutil.rmtree(cfg.folder, ignore_errors=True)
        self._save()

    def register_console_callback(self, name, callback):
        callbacks = self.console_callbacks.setdefault(name, [])
        if callback not in callbacks:
            callbacks.append(callback)

    def unregister_console_callbacks(self, name):
        self.console_callbacks.pop(name, None)

    def _json_list(self, name, filename):
        cfg = self.servers.get(name)
        if not cfg:
            return []
        path = Path(cfg.folder) / filename
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _json_add(self, name, filename, entry):
        cfg = self.servers.get(name)
        if not cfg:
            return
        values = self._json_list(name, filename)
        if not any(item.get("name") == entry.get("name") for item in values):
            values.append(entry)
        (Path(cfg.folder) / filename).write_text(json.dumps(values, indent=2), encoding="utf-8")

    def _json_remove(self, name, filename, player):
        cfg = self.servers.get(name)
        if not cfg:
            return
        values = [item for item in self._json_list(name, filename) if item.get("name") != player]
        (Path(cfg.folder) / filename).write_text(json.dumps(values, indent=2), encoding="utf-8")

    def get_whitelist(self, name):
        return self._json_list(name, "whitelist.json")

    def add_whitelist(self, name, player):
        self._json_add(name, "whitelist.json", {"name": player, "uuid": ""})

    def remove_whitelist(self, name, player):
        self._json_remove(name, "whitelist.json", player)

    def get_ops(self, name):
        return self._json_list(name, "ops.json")

    def add_op(self, name, player):
        self._json_add(name, "ops.json", {"name": player, "uuid": "", "level": 4, "bypassesPlayerLimit": False})

    def remove_op(self, name, player):
        self._json_remove(name, "ops.json", player)

    def get_banned_players(self, name):
        return self._json_list(name, "banned-players.json")

    def ban_player(self, name, player):
        self._json_add(name, "banned-players.json", {"name": player, "uuid": "", "reason": "Banned by operator"})

    def unban_player(self, name, player):
        self._json_remove(name, "banned-players.json", player)

    def get_plugins_dir(self, name) -> Optional[Path]:
        cfg = self.servers.get(name)
        if not cfg:
            return None
        return Path(cfg.folder) / ("mods" if cfg.loader in ("fabric", "forge", "neoforge") else "plugins")

    def list_plugins(self, name):
        directory = self.get_plugins_dir(name)
        if not directory or not directory.exists():
            return []
        return [p.name for p in sorted(directory.iterdir()) if p.suffix.lower() == ".jar"]

    def add_plugin(self, name, jar_path):
        directory = self.get_plugins_dir(name)
        if directory:
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(jar_path, directory / Path(jar_path).name)

    def remove_plugin(self, name, plugin_name):
        directory = self.get_plugins_dir(name)
        if directory and (directory / plugin_name).exists():
            (directory / plugin_name).unlink()

    def _safe_path(self, name, rel_path):
        cfg = self.servers.get(name)
        if not cfg:
            return None
        root = Path(cfg.folder).resolve()
        target = (root / rel_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None
        return target

    def list_files(self, name, subpath=""):
        cfg = self.servers.get(name)
        base = self._safe_path(name, subpath)
        if not cfg or not base or not base.exists():
            return []
        root = Path(cfg.folder).resolve()
        return [
            {
                "name": p.name,
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
                "path": str(p.relative_to(root)),
            }
            for p in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        ]

    def read_file(self, name, rel_path):
        target = self._safe_path(name, rel_path)
        if not target:
            return ""
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def write_file(self, name, rel_path, content):
        target = self._safe_path(name, rel_path)
        if not target:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True

    def delete_file(self, name, rel_path):
        target = self._safe_path(name, rel_path)
        if not target:
            return False
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return True
