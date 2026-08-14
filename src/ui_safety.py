"""Safety helpers for destructive MineHoster UI actions."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Optional


def safe_delete_server(server_dir: Path, allowed_root: Path) -> None:
    """Delete one server directory, refusing paths outside MineHoster's server root."""
    server_dir = server_dir.resolve()
    allowed_root = allowed_root.resolve()
    try:
        server_dir.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("Refusing to delete a path outside the server directory") from exc
    if server_dir == allowed_root or not server_dir.exists():
        return
    shutil.rmtree(server_dir)


def full_reset(root: Path, confirm: str, on_close: Optional[Callable[[], None]] = None) -> bool:
    """Delete MineHoster data only after an explicit RESET confirmation."""
    if confirm.strip() != "RESET":
        return False
    root = root.resolve()
    home = Path.home().resolve()
    # Refuse obviously dangerous roots and never allow filesystem root deletion.
    if root in {Path("/"), home, Path(root.anchor)}:
        raise ValueError("Refusing to reset an unsafe root directory")
    if root.exists():
        shutil.rmtree(root)
    if on_close:
        on_close()
    return True
