import os
import platform
import shutil
import subprocess
import tarfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

RUNTIMES_DIR = Path.home() / ".minehoster" / "runtimes"
ADOPTIUM_API = "https://api.adoptium.net/v3/binary/latest/{version}/ga/{os_name}/{arch}/jre/hotspot/normal/eclipse"
USER_AGENT = "MineHoster/2.0 (https://github.com/viperxc24odmaker/Mine-Hoster)"
_INSTALL_LOCK = threading.Lock()


def _platform_target():
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows": os_name = "windows"
    elif system == "darwin": os_name = "mac"
    elif system == "linux": os_name = "linux"
    else: raise RuntimeError(f"Automatic Java installation is not supported on {system}.")
    if machine in ("amd64", "x86_64", "x64"): arch = "x64"
    elif machine in ("arm64", "aarch64"): arch = "aarch64"
    else: raise RuntimeError(f"Automatic Java installation is not supported for {machine}.")
    return os_name, arch


def _java_binary(root: Path) -> Path:
    return root / "bin" / ("java.exe" if os.name == "nt" else "java")


def _java_version(command: str) -> Optional[int]:
    try:
        result = subprocess.run([command, "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout or ""
    marker = 'version "'
    if marker not in output: return None
    raw = output.split(marker, 1)[1].split('"', 1)[0]
    try: return int(raw.split(".")[1]) if raw.startswith("1.") else int(raw.split(".")[0])
    except (ValueError, IndexError): return None


def _download(url: str, target: Path, progress_cb: Optional[Callable] = None, label: str = "Downloading"):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        total = int(response.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk: break
            output.write(chunk)
            done += len(chunk)
            if progress_cb:
                percent = min(100, int(done * 100 / total)) if total else None
                progress_cb("progress", f"{label}... {percent}%" if percent is not None else f"{label}...", percent)


def _extract_archive(archive: Path, destination: Path):
    temporary = destination.with_name(destination.name + ".extracting")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True, exist_ok=True)
    try:
        if archive.suffix.lower() == ".zip":
            with zipfile.ZipFile(archive) as zf: zf.extractall(temporary)
        else:
            with tarfile.open(archive, "r:gz") as tf: tf.extractall(temporary)
        roots = [p for p in temporary.iterdir() if p.is_dir()]
        source = roots[0] if len(roots) == 1 else temporary
        if not _java_binary(source).exists():
            matches = list(temporary.rglob("java.exe" if os.name == "nt" else "java"))
            if not matches: raise RuntimeError("Downloaded Java archive does not contain a runnable Java runtime.")
            source = matches[0].parent.parent
        shutil.rmtree(destination, ignore_errors=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def installed_jres():
    result = []
    if not RUNTIMES_DIR.exists(): return result
    for path in sorted(RUNTIMES_DIR.iterdir()):
        if path.is_dir():
            java = _java_binary(path)
            version = _java_version(str(java)) if java.exists() else None
            if version: result.append((version, str(java), path))
    return result


def download_java(required: int, progress_cb: Optional[Callable] = None) -> str:
    """Manually download and install a private Eclipse Temurin JRE."""
    os_name, arch = _platform_target()
    runtime_root = RUNTIMES_DIR / f"temurin-{required}-{os_name}-{arch}"
    local_java = _java_binary(runtime_root)
    with _INSTALL_LOCK:
        if _java_version(str(local_java)) == required:
            if progress_cb: progress_cb("done", f"JRE {required} is already installed.", 100)
            return str(local_java)
        RUNTIMES_DIR.mkdir(parents=True, exist_ok=True)
        if progress_cb: progress_cb("downloading", f"Downloading Eclipse Temurin JRE {required} ({os_name}/{arch})...", 0)
        archive_suffix = ".zip" if os_name == "windows" else ".tar.gz"
        archive = RUNTIMES_DIR / f"temurin-{required}-{os_name}-{arch}{archive_suffix}.part"
        try:
            url = ADOPTIUM_API.format(version=required, os_name=os_name, arch=arch)
            _download(url, archive, progress_cb, f"Downloading JRE {required}")
            if archive.stat().st_size < 1024 * 1024: raise RuntimeError("Downloaded JRE archive is unexpectedly small.")
            if progress_cb: progress_cb("installing", f"Installing JRE {required}...", 100)
            _extract_archive(archive, runtime_root)
        finally:
            archive.unlink(missing_ok=True)
    if _java_version(str(local_java)) != required:
        raise RuntimeError(f"JRE {required} was downloaded, but could not be verified.")
    if progress_cb: progress_cb("done", f"JRE {required} is ready.", 100)
    return str(local_java)


def ensure_java(required: int, progress_cb: Optional[Callable] = None) -> str:
    """Find a matching Java runtime or download a private Temurin JRE automatically."""
    env_names = [f"JAVA_HOME_{required}_X64", f"JAVA_HOME_{required}", "JAVA_HOME"]
    candidates = []
    for name in env_names:
        home = os.environ.get(name)
        if home: candidates.append(str(Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")))
    candidates.append("java")
    if os.name == "nt":
        for root_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(root_name)
            if not root: continue
            for base_name in ("Java", "Eclipse Adoptium", "Amazon Corretto"):
                base = Path(root) / base_name
                if base.exists():
                    candidates.extend(str(p / "bin" / "java.exe") for p in sorted(base.iterdir(), reverse=True) if p.is_dir())
    for candidate in dict.fromkeys(candidates):
        if _java_version(candidate) == required: return candidate
    return download_java(required, progress_cb)
