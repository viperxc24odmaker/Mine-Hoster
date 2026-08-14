"""Explicit reset/delete planning so destructive UI actions are reviewable."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResetPlan:
    root: Path
    server_count: int
    delete_servers: bool = True
    delete_cache: bool = True
    close_app: bool = True

    @property
    def description(self) -> str:
        return (
            f"Delete MineHoster data at {self.root} including {self.server_count} server(s), "
            "managed downloads/JRE cache, then close the application."
        )
