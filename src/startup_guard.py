"""Startup resilience for MineHoster server processes.

A few server distributions can exit during their first boot because they finish
one-time initialization after the Java process has been spawned.  This guard
retries one unexpected early exit once, while never interfering with an
explicit stop requested by the user.
"""

import threading
import time

from src import server_manager as _server_manager

_ORIGINAL_START = _server_manager.ServerManager.start_server
_GUARD_LOCK = threading.Lock()
_GUARDED_STARTS = set()


def _retry_after_unexpected_exit(manager, name):
    # Give the server enough time to print its normal startup output.  We only
    # retry once and only when the process disappears without an explicit stop.
    time.sleep(8)
    with _GUARD_LOCK:
        if name not in _GUARDED_STARTS:
            return
        _GUARDED_STARTS.discard(name)

    if name not in manager.servers or manager.is_running(name):
        return

    manager._emit(name, "[MineHoster] Server exited during first startup; retrying once...")
    try:
        started = _ORIGINAL_START(manager, name)
    except Exception as exc:
        manager._emit(name, f"[ERROR] Automatic startup retry failed: {exc}")
        return
    if not started:
        manager._emit(name, "[ERROR] Automatic startup retry could not launch the server.")


def resilient_start(self, name):
    result = _ORIGINAL_START(self, name)
    if not result:
        return result

    with _GUARD_LOCK:
        _GUARDED_STARTS.add(name)
    threading.Thread(
        target=_retry_after_unexpected_exit,
        args=(self, name),
        daemon=True,
        name=f"MineHoster-start-guard-{name}",
    ).start()
    return result


def cancel_start_guard(name):
    with _GUARD_LOCK:
        _GUARDED_STARTS.discard(name)


_server_manager.ServerManager.start_server = resilient_start
_original_stop = _server_manager.ServerManager.stop_server


def resilient_stop(self, name):
    cancel_start_guard(name)
    return _original_stop(self, name)


_server_manager.ServerManager.stop_server = resilient_stop
