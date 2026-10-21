"""Tiny reloader: run the dashboard in a child process and restart it when the package's Python changes.

The MCP server starts this as a subprocess, so a code change reloads the dashboard without
restarting the MCP server (which would disconnect its tools in Claude Code). With `parent_pid`
it also exits when that process is gone, so a crashed MCP server never leaves the port taken.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
POLL_S = 1.0
RETRY_S = 10.0  # retry a dashboard that exited (e.g. port busy) this often


def snapshot(root: Path = PACKAGE_DIR) -> dict[str, float]:
    return {str(p): p.stat().st_mtime for p in root.rglob("*.py") if "__pycache__" not in p.parts}


def changed(before: dict[str, float], after: dict[str, float]) -> list[str]:
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: still running
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # signal 0 only checks; it does not terminate on POSIX
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def exit_with_parent(pid: int) -> None:
    """Hard-exit this process once `pid` is gone (a killed supervisor can't stop its child itself)."""
    import threading

    def watch() -> None:
        while pid_alive(pid):
            time.sleep(POLL_S)
        os._exit(0)

    threading.Thread(target=watch, name="parent-watch", daemon=True).start()


def _log(msg: str) -> None:
    print(f"[reload] {msg}", file=sys.stderr, flush=True)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None and sys.platform == "win32":
        # A venv's python.exe is a launcher that runs the real interpreter as its child, so
        # terminating the launcher alone would leave the dashboard holding the port.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def supervise(cmd: list[str], parent_pid: int | None = None) -> int:
    # The child must not write to our stdout: under the MCP server, stdout is the protocol channel.
    def start() -> subprocess.Popen:
        return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    state = snapshot()
    proc = start()
    _log(f"watching {PACKAGE_DIR}")
    try:
        while True:
            time.sleep(POLL_S)
            if parent_pid and not pid_alive(parent_pid):
                _log("parent exited; stopping")
                return 0
            now = snapshot()
            diff = changed(state, now)
            if diff:
                state = now
                more = f" +{len(diff) - 1} more" if len(diff) > 1 else ""
                _log(f"{Path(diff[0]).name}{more} changed; restarting")
                _stop(proc)
                proc = start()
            elif proc.poll() is not None:
                # Exited: a syntax error mid-edit, or the port is taken by another dashboard. Retry on
                # the next change, or after RETRY_S so it takes over once the port is free.
                _log(f"dashboard exited with {proc.returncode}; retrying on the next change or in {RETRY_S:.0f} s")
                deadline = time.monotonic() + RETRY_S
                while not changed(state, now := snapshot()) and time.monotonic() < deadline:
                    time.sleep(POLL_S)
                    if parent_pid and not pid_alive(parent_pid):
                        return 0
                state = now
                proc = start()
    except KeyboardInterrupt:
        return 0
    finally:
        _stop(proc)
