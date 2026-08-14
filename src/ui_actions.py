"""Reusable UI action contracts for MineHoster views.

Views can use these small helpers to keep destructive actions explicit and
avoid duplicating confirmation/disabled-state logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ActionState:
    label: str
    enabled: bool = True
    busy: bool = False


def destructive_state(label: str, busy: bool = False) -> ActionState:
    return ActionState(label=label, enabled=not busy, busy=busy)


def confirm_text(value: str, expected: str = "RESET") -> bool:
    return value.strip().upper() == expected.upper()


def run_after_confirmation(value: str, action: Callable[[], None], expected: str = "RESET") -> bool:
    if not confirm_text(value, expected):
        return False
    action()
    return True
