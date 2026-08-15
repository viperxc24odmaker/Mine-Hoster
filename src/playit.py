import os, platform, re, subprocess, threading, urllib.request
from pathlib import Path
from typing import Callable, Optional
PLAYIT_DIR=Path.home()/".minehoster"/"playit"; PLAYIT_EXE=PLAYIT_DIR/("playit.exe" if os.name=="nt" else "playit"); PLAYIT_VERSION="1.0.10"; USER_AGENT="MineHoster/2.1"
def _download_url():
    system=platform.system().lower(); machine=platform.machine().lower()
    if system=="windows" and machine in ("amd64","x86_64","x64"):return f"https://github.com/playit-cloud/playit-agent/releases/download/v{PLAYIT_VERSION}/playit-windows-x86_64-signed.exe"
    if system=="linux" and machine in ("amd64","x86_64","x64"):return f"https://github.com/playit-cloud/playit-agent/releases/download/v{PLAYIT_VERSION}/playit-linux-amd64"
    if system=="darwin" and machine in ("arm64","aarch64"):return f"https://github.com/playit-cloud/playit-agent/releases/download/v{PLAYIT_VERSION}/playit-macos-aarch64"
    if system=="darwin":return f"https://github.com/playit-cloud/playit-agent/releases/download/v{PLAYIT_VERSION}/playit-macos-amd64"
    raise RuntimeError(f"Automatic Playit installation is not supported on {system}/{machine}.")
def _proc_flags():return {"creationflags":getattr(subprocess,"CREATE_NO_WINDOW",0)} if os.name=="nt" else {}
class PlayitManager:
    _instance=None
    @classmethod
    def get(cls):
        if cls._instance is None:cls._instance=cls()
        return cls._instance
    def __init__(self):self.process=None;self.running=False;self.tunnel_address="";self.claim_url="";self.setup_output="";self.log_callbacks=[];PLAYIT_DIR.mkdir(parents=True,exist_ok=True)
    def is_installed(self):
        try:return PLAYIT_EXE.is_file() and PLAYIT_EXE.stat().st_size>100*1024
        except OSError:return False
    def install(self,progress_cb=None):
        if self.is_installed():
            if progress_cb:progress_cb("already_installed",f"Playit.gg agent {PLAYIT_VERSION} is already installed.",100)
            return True
        part=PLAYIT_EXE.with_suffix(PLAYIT_EXE.suffix+".part")
        try:
            if progress_cb:progress_cb("downloading",f"Downloading official Playit.gg {PLAYIT_VERSION}...",0)
            req=urllib.request.Request(_download_url(),headers={"User-Agent":USER_AGENT});
            with urllib.request.urlopen(req,timeout=120) as r,part.open("wb") as out:
                total=int(r.headers.get("Content-Length",0) or 0);done=0
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk:break
                    out.write(chunk);done+=len(chunk)
                    if progress_cb and total:progress_cb("progress",f"Downloading Playit.gg... {done*100//total}%",min(100,done*100//total))
            if part.stat().st_size<100*1024:raise RuntimeError("Playit download is incomplete.")
            part.replace(PLAYIT_EXE)
            if os.name!="nt":PLAYIT_EXE.chmod(PLAYIT_EXE.stat().st_mode|0o111)
            if progress_cb:progress_cb("done",f"Playit.gg {PLAYIT_VERSION} installed.",100)
            return True
        except Exception as exc:
            part.unlink(missing_ok=True)
            if progress_cb:progress_cb("error",f"Playit download failed: {exc}",0)
            return False
    def _emit(self,line):
        self.setup_output=(self.setup_output+line+"\n")[-12000:];lower=line.lower();m=re.search(r"https?://[^\s]+",line)
        if m and ("playit" in m.group(0).lower() or "claim" in lower or "setup" in lower):self.claim_url=m.group(0).rstrip(".,)")
        for token in line.split():
            clean=token.strip("[](),:;\"")
            if any(x in clean for x in (".joinmc.link",".gl.at.ply.gg",".playit.gg")):self.tunnel_address=clean;break
        for cb in list(self.log_callbacks):
            try:cb(line)
            except Exception:pass
    def _reader(self,process):
        try:
            if process.stdout:
                for line in process.stdout:self._emit(line.rstrip("\r\n"))
        finally:
            self.running=False
            if self.process is process:self.process=None
    def setup(self,setup_code="",callback=None):
        if not self.is_installed() and not self.install(callback):return False
        if self.running:return False
        self.claim_url="";self.setup_output=""
        try:
            self.process=subprocess.Popen([str(PLAYIT_EXE),"-s","setup"],cwd=str(PLAYIT_DIR),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",bufsize=1,**_proc_flags());self.running=True;threading.Thread(target=self._reader,args=(self.process,),daemon=True).start()
            if setup_code.strip() and self.process.stdin:self.process.stdin.write(setup_code.strip()+"\n");self.process.stdin.flush()
            return True
        except Exception as exc:self._emit(f"[ERROR] Playit setup failed: {exc}");self.running=False;return False
    def start(self,port=25565,bedrock=False):
        if not self.is_installed():self._emit("[ERROR] Playit.gg is not installed.");return False
        if self.running:return True
        try:
            self._emit(f"[MineHoster] Starting Playit agent for local port {port} ({'UDP' if bedrock else 'TCP'}).")
            self.process=subprocess.Popen([str(PLAYIT_EXE),"-s"],cwd=str(PLAYIT_DIR),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,text=True,encoding="utf-8",errors="replace",bufsize=1,**_proc_flags());self.running=True;threading.Thread(target=self._reader,args=(self.process,),daemon=True).start();return True
        except Exception as exc:self._emit(f"[ERROR] Could not start Playit agent: {exc}");self.running=False;return False
    def stop(self):
        if self.process:
            try:self.process.terminate()
            except OSError:pass
        self.process=None;self.running=False
    def register_callback(self,callback):
        if callback not in self.log_callbacks:self.log_callbacks.append(callback)
    def unregister_callbacks(self):self.log_callbacks.clear()
    def status(self):return {"installed":self.is_installed(),"running":self.running,"claim_url":self.claim_url,"tunnel_address":self.tunnel_address,"output":self.setup_output}
