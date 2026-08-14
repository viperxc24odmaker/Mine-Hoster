import subprocess
import threading
import urllib.request
import toml
from pathlib import Path
from typing import Callable

PLAYIT_DIR = Path.home() / ".minehoster" / "playit"
PLAYIT_EXE = PLAYIT_DIR / "playit.exe"
PLAYIT_CONFIG = PLAYIT_DIR / "playit.toml"
PLAYIT_DOWNLOAD = "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-windows-x86_64-signed.exe"


def _write_config(port: int, protocol: str = "tcp"):
    """
    Write a minimal playit.toml config that creates a Minecraft tunnel
    automatically without any manual browser setup.
    protocol: 'tcp' for Java, 'udp' for Bedrock
    """
    # playit.gg config format for agent v0.15+
    config = {
        "last_update": 0,
        "ping_targets": ["ping1.playit.gg", "ping2.playit.gg"],
        "secret_key": "",  # empty = generate new key on first run, opens browser for claim
        "tunnels": [
            {
                "id": "",
                "name": "minehoster-tunnel",
                "proto": protocol,
                "port_type": protocol,
                "port_count": 1,
                "local_ip": "127.0.0.1",
                "local_port": port,
                "tunnel_type": "minecraft-java" if protocol == "tcp" else "minecraft-bedrock",
            }
        ]
    }
    PLAYIT_CONFIG.write_text(toml.dumps(config))


class PlayitManager:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.tunnel_address: str = ""
        self.running = False
        self.log_callbacks: list[Callable] = []
        PLAYIT_DIR.mkdir(parents=True, exist_ok=True)

    def is_installed(self) -> bool:
        return PLAYIT_EXE.exists()

    def install(self, progress_cb: Callable = None) -> bool:
        if self.is_installed():
            if progress_cb:
                progress_cb("already_installed", "playit.gg already installed")
            return True
        try:
            if progress_cb:
                progress_cb("downloading", "Downloading playit.gg agent...")

            def reporthook(count, block_size, total_size):
                if total_size > 0 and progress_cb:
                    pct = int(count * block_size * 100 / total_size)
                    progress_cb("progress", f"Downloading playit.gg... {min(pct,100)}%")

            urllib.request.urlretrieve(PLAYIT_DOWNLOAD, PLAYIT_EXE, reporthook)
            if progress_cb:
                progress_cb("done", "playit.gg installed!")
            return True
        except Exception as e:
            if progress_cb:
                progress_cb("error", f"Failed to download playit.gg: {e}")
            return False

    def start(self, port: int = 25565, bedrock: bool = False):
        if self.running:
            return
        if not self.is_installed():
            return

        protocol = "udp" if bedrock else "tcp"
        _write_config(port, protocol)

        self.running = True
        self.process = subprocess.Popen(
            [str(PLAYIT_EXE), "--config", str(PLAYIT_CONFIG)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        if not self.process:
            return
        for line in self.process.stdout:
            line = line.rstrip()
            # Parse tunnel address from playit output
            lower = line.lower()
            if (
                ".joinmc.link" in line
                or ".playit.gg" in line
                or "connect to" in lower
                or "address:" in lower
                or "tunnel address" in lower
            ):
                # Try to extract just the address part
                for part in line.split():
                    if ".joinmc.link" in part or ".playit.gg" in part:
                        self.tunnel_address = part.strip()
                        break
                if not self.tunnel_address:
                    self.tunnel_address = line

            for cb in self.log_callbacks:
                cb(line)

        self.running = False
        self.tunnel_address = ""
        for cb in self.log_callbacks:
            cb("[playit.gg] Disconnected.")

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None
        self.running = False
        self.tunnel_address = ""

    def register_callback(self, cb: Callable):
        self.log_callbacks.append(cb)

    def unregister_callbacks(self):
        self.log_callbacks.clear()
