import os
import platform
import re
import subprocess
import threading
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, Optional

PLAYIT_DIR = Path.home() / ".minehoster" / "playit"
PLAYIT_EXE = PLAYIT_DIR / ("playit.exe" if os.name == "nt" else "playit")
PLAYIT_CONFIG = PLAYIT_DIR / "playit.toml"
TUNNEL_ADDRESS_FILE = PLAYIT_DIR / "tunnel_address.txt"
USER_AGENT = "MineHoster/2.1 (https://github.com/viperxc24odmaker/Mine-Hoster)"


def _download_url() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in ("amd64", "x86_64", "x64"):
        return "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-windows-x86_64-signed.exe"
    if system == "linux" and machine in ("amd64", "x86_64", "x64"):
        return "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-amd64"
    if system == "darwin" and machine in ("arm64", "aarch64"):
        return "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-macos-aarch64"
    if system == "darwin":
        return "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-macos-amd64"
    raise RuntimeError(f"Automatic Playit installation is not supported on {system}/{machine}.")


class PlayitManager:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.tunnel_address = self._load_saved_address()
        self.claim_url = ""
        self.setup_output = ""
        self.log_callbacks: list[Callable] = []
        self._lock = threading.Lock()
        PLAYIT_DIR.mkdir(parents=True, exist_ok=True)

    def _load_saved_address(self):
        try:
            return TUNNEL_ADDRESS_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _save_address(self, address):
        address = (address or "").strip()
        if address:
            TUNNEL_ADDRESS_FILE.write_text(address + "\n", encoding="utf-8")
            self.tunnel_address = address

    def is_installed(self) -> bool:
        try:
            return PLAYIT_EXE.exists() and PLAYIT_EXE.stat().st_size > 100 * 1024
        except OSError:
            return False

    def has_secret(self) -> bool:
        try:
            text = PLAYIT_CONFIG.read_text(encoding="utf-8", errors="ignore")
            return bool(re.search(r"(?:secret|secret_key)\s*=\s*[\"']([^\"']+)[\"']", text))
        except OSError:
            return False

    def install(self, progress_cb: Optional[Callable] = None) -> bool:
        if self.is_installed():
            if progress_cb:
                progress_cb("already_installed", "Playit.gg agent is already installed.", 100)
            return True
        PLAYIT_DIR.mkdir(parents=True, exist_ok=True)
        part = PLAYIT_EXE.with_suffix(PLAYIT_EXE.suffix + ".part")
        try:
            url = _download_url()
            if progress_cb:
                progress_cb("downloading", "Downloading the official Playit.gg agent...", 0)
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as output:
                total = int(response.headers.get("Content-Length", 0) or 0)
                done = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    done += len(chunk)
                    if progress_cb and total:
                        progress_cb("progress", f"Downloading Playit.gg agent... {int(done * 100 / total)}%", min(100, int(done * 100 / total)))
            if part.stat().st_size < 100 * 1024:
                raise RuntimeError("Playit download was unexpectedly small or incomplete.")
            part.replace(PLAYIT_EXE)
            if os.name != "nt":
                PLAYIT_EXE.chmod(PLAYIT_EXE.stat().st_mode | 0o111)
            if progress_cb:
                progress_cb("done", "Playit.gg agent installed successfully.", 100)
            return True
        except Exception as exc:
            part.unlink(missing_ok=True)
            if progress_cb:
                progress_cb("error", f"Playit download failed: {exc}", 0)
            return False

    def _emit(self, line: str):
        self.setup_output = (self.setup_output + line + "\n")[-16000:]
        lower = line.lower()
        match = re.search(r"https?://[^\s]+", line)
        if match:
            url = match.group(0).rstrip(".,)")
            if "playit.gg/claim/" in url or "playit.gg/mc" in url:
                self.claim_url = url
        # Playit has emitted several public-address formats over time. Keep the
        # parser deliberately conservative so normal log URLs are not mistaken
        # for tunnel endpoints.
        for token in line.split():
            clean = token.strip("[](),:;\"")
            if any(host in clean for host in (".joinmc.link", ".gl.at.ply.gg", ".playit.gg")) and not clean.startswith("https://playit.gg"):
                self._save_address(clean)
                break
        for callback in list(self.log_callbacks):
            try:
                callback(line)
            except Exception:
                pass

    def _reader(self, process: subprocess.Popen):
        try:
            if process.stdout:
                for line in process.stdout:
                    self._emit(line.rstrip("\r\n"))
        finally:
            self.running = False
            if self.process is process:
                self.process = None

    def setup(self, setup_code: str = "", callback: Optional[Callable] = None) -> bool:
        if not self.is_installed() and not self.install(callback):
            return False
        if self.running:
            self._emit("[MineHoster] Playit is already running.")
            return True
        self.claim_url = ""
        self.setup_output = ""
        try:
            self._emit("[MineHoster] Starting official Playit agent setup...")
            process = subprocess.Popen([str(PLAYIT_EXE), "-s", "setup"], cwd=str(PLAYIT_DIR), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
            self.process = process
            self.running = True
            threading.Thread(target=self._reader, args=(process,), daemon=True, name="MineHoster-PlayitSetup").start()
            if setup_code.strip() and process.stdin:
                process.stdin.write(setup_code.strip() + "\n")
                process.stdin.flush()
            return True
        except Exception as exc:
            self._emit(f"[ERROR] Playit setup failed: {exc}")
            self.running = False
            return False

    def open_claim(self):
        if self.claim_url:
            try:
                webbrowser.open(self.claim_url)
                return True
            except Exception:
                return False
        return False

    def open_tunnel_setup(self):
        try:
            webbrowser.open("https://playit.gg/account/setup/new-tunnel")
            return True
        except Exception:
            return False

    def start(self, port: int = 25565, bedrock: bool = False, secret: str = "") -> bool:
        if not self.is_installed() and not self.install():
            return False
        if self.running:
            return True
        try:
            if secret.strip():
                # Official agent deployments support --secret for headless setup.
                cmd = [str(PLAYIT_EXE), "--stdout", "--secret", secret.strip()]
            else:
                cmd = [str(PLAYIT_EXE), "-s"]
            self._emit(f"[MineHoster] Starting Playit agent for local port {port} ({'Bedrock/UDP' if bedrock else 'Minecraft Java'}).")
            self.process = subprocess.Popen(cmd, cwd=str(PLAYIT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
            self.running = True
            threading.Thread(target=self._reader, args=(self.process,), daemon=True, name="MineHoster-Playit").start()
            return True
        except Exception as exc:
            self._emit(f"[ERROR] Could not start Playit agent: {exc}")
            self.running = False
            return False

    def stop(self):
        process = self.process
        if process:
            try:
                process.terminate()
            except OSError:
                pass
        self.process = None
        self.running = False

    def register_callback(self, callback: Callable):
        if callback not in self.log_callbacks:
            self.log_callbacks.append(callback)

    def unregister_callbacks(self):
        self.log_callbacks.clear()

    def status(self) -> dict:
        return {"installed": self.is_installed(), "running": self.running, "claimed": self.has_secret(), "claim_url": self.claim_url, "tunnel_address": self.tunnel_address, "output": self.setup_output}
