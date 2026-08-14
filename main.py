import os
import subprocess
from pathlib import Path
import flet as ft
from src.app import MineHosterApp
from src import server_manager as _server_manager
from src.java_runtime import ensure_java as _real_ensure_java


def _cached_ensure_java(required, progress_cb=None):
    """Reuse MineHoster's private runtime across app restarts before downloading."""
    runtime_dir = Path.home() / ".minehoster" / "runtimes"
    exe = "java.exe" if os.name == "nt" else "java"
    prefixes = [runtime_dir / f"temurin-{required}-windows-x64", runtime_dir / f"temurin-{required}-linux-x64", runtime_dir / f"temurin-{required}-mac-x64", runtime_dir / f"temurin-{required}-windows-aarch64", runtime_dir / f"temurin-{required}-linux-aarch64", runtime_dir / f"temurin-{required}-mac-aarch64"]
    for root in prefixes:
        java = root / "bin" / exe
        if not java.is_file():
            continue
        try:
            result = subprocess.run([str(java), "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
            output = result.stdout or ""
            marker = 'version "'
            if marker in output:
                raw = output.split(marker, 1)[1].split('"', 1)[0]
                detected = int(raw.split(".")[1]) if raw.startswith("1.") else int(raw.split(".")[0])
                if detected == required:
                    if progress_cb:
                        progress_cb("done", f"JRE {required} found in MineHoster runtime cache. Reusing it.", 100)
                    return str(java)
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            pass
    return _real_ensure_java(required, progress_cb)


_server_manager.ensure_java = _cached_ensure_java
_server_manager._find_java = _cached_ensure_java


def main(page: ft.Page):
    app = MineHosterApp(page)
    app.initialize()


ft.app(target=main)
