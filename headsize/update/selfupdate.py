"""Swap the running build for a freshly downloaded one.

Portable single-file builds make an update a file replacement, but the running
image is locked by the OS, so the work is delegated to a small script that is
spawned detached:

1. wait (bounded) for our PID to exit,
2. rename the current build aside as ``*.old``,
3. move the new build into place (retrying while an AV scanner holds it),
4. relaunch, delete the script, and drop the ``*.old`` backup.

Nothing here touches user data: only the executable path is replaced.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

#: Seconds the helper script waits for the app to exit before giving up.
WAIT_SECONDS = 90
#: Attempts to replace the binary (antivirus scanners briefly lock new files).
REPLACE_ATTEMPTS = 60

_WINDOWS_SCRIPT = r"""@echo off
setlocal enableextensions
set "TARGET=%~1"
set "PAYLOAD=%~2"
set "PID=%~3"
set "BACKUP=%TARGET%.old"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=%PID%; for($i=0;$i -lt {wait_steps};$i++){{ if(-not (Get-Process -Id $p -ErrorAction SilentlyContinue)){{break}}; Start-Sleep -Milliseconds 250 }}" >nul 2>&1
move /Y "%TARGET%" "%BACKUP%" >nul 2>&1
set /a tries=0
:retry
move /Y "%PAYLOAD%" "%TARGET%" >nul 2>&1
if not errorlevel 1 goto :launch
set /a tries+=1
if %tries% GEQ {attempts} goto :rollback
ping -n 2 127.0.0.1 >nul 2>&1
goto :retry
:rollback
move /Y "%BACKUP%" "%TARGET%" >nul 2>&1
del "%~f0" >nul 2>&1
exit /b 1
:launch
del "%BACKUP%" >nul 2>&1
start "" "%TARGET%"
del "%~f0" >nul 2>&1
exit /b 0
"""

_POSIX_SCRIPT = r"""#!/bin/sh
# POSIX self-update helper
TARGET="$1"
PAYLOAD="$2"
PID="$3"
i=0
while [ "$i" -lt {wait_steps} ]; do
    if ! kill -0 "$PID" 2>/dev/null; then break; fi
    sleep 0.5
    i=$((i + 1))
done
mv -f "$TARGET" "$TARGET.old" 2>/dev/null
i=0
while [ "$i" -lt {attempts} ]; do
    if mv -f "$PAYLOAD" "$TARGET" 2>/dev/null; then
        chmod +x "$TARGET" 2>/dev/null
        rm -f "$TARGET.old"
        ( "$TARGET" >/dev/null 2>&1 & )
        rm -f "$0"
        exit 0
    fi
    sleep 1
    i=$((i + 1))
done
mv -f "$TARGET.old" "$TARGET" 2>/dev/null
rm -f "$0"
exit 1
"""


class SelfUpdateError(RuntimeError):
    """Raised when the running build cannot be replaced."""


def current_executable() -> Path | None:
    """Path of the frozen executable, or ``None`` when running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return None


def supports_self_update() -> bool:
    """True when the app can replace itself (frozen build in a writable dir)."""
    target = current_executable()
    if target is None or not target.is_file():
        return False
    return os.access(target.parent, os.W_OK)


def build_helper_script(*, windows: bool | None = None) -> str:
    """The helper script text (exposed for tests and diagnostics)."""
    is_windows = os.name == "nt" if windows is None else windows
    template = _WINDOWS_SCRIPT if is_windows else _POSIX_SCRIPT
    return template.format(
        wait_steps=int(WAIT_SECONDS * 4),
        attempts=int(REPLACE_ATTEMPTS),
    )


def write_helper_script(payload: Path) -> Path:
    """Write the helper next to ``payload`` and return its path."""
    is_windows = os.name == "nt"
    suffix = ".cmd" if is_windows else ".sh"
    path = payload.with_name(payload.name + ".update" + suffix)
    path.write_text(build_helper_script(), encoding="utf-8", newline="\n")
    if not is_windows:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def apply_update(
    payload: str | Path,
    *,
    target: str | Path | None = None,
    pid: int | None = None,
) -> Path:
    """Launch the detached helper that replaces ``target`` with ``payload``.

    The caller must quit the application right after this returns; the helper
    waits for the process to exit before touching the file. ``pid`` defaults to
    the current process and exists so tests can simulate an exited app.
    """
    payload_path = Path(payload)
    if not payload_path.is_file():
        raise SelfUpdateError(f"Update payload not found: {payload_path}")
    if payload_path.stat().st_size == 0:
        raise SelfUpdateError("Update payload is empty.")

    target_path = Path(target) if target else current_executable()
    if target_path is None:
        raise SelfUpdateError(
            "Running from source: self-update is disabled, download the release instead."
        )
    if not target_path.is_file():
        raise SelfUpdateError(f"Current executable not found: {target_path}")

    script = write_helper_script(payload_path)
    if pid is None:
        pid = os.getpid()
    if os.name == "nt":
        creation = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
        subprocess.Popen(  # noqa: S603
            ["cmd", "/c", str(script), str(target_path), str(payload_path), str(pid)],
            creationflags=creation,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(  # noqa: S603
            ["/bin/sh", str(script), str(target_path), str(payload_path), str(pid)],
            start_new_session=True,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return script


def cleanup_leftovers(new_version: str = "") -> list[Path]:
    """Remove ``*.old`` backups and stale payloads from the app directory.

    Called on startup: a failed update leaves the backup behind so the user can
    roll back manually, and a successful one leaves nothing at all.
    """
    target = current_executable()
    if target is None:
        return []
    removed: list[Path] = []
    for candidate in target.parent.glob(target.name + ".old"):
        try:
            candidate.unlink()
            removed.append(candidate)
        except OSError:
            pass
    for pattern in ("*.update.cmd", "*.update.sh", "*.download"):
        for candidate in target.parent.glob(pattern):
            try:
                candidate.unlink()
                removed.append(candidate)
            except OSError:
                pass
    if new_version:
        for candidate in target.parent.glob(f"{target.stem}-{new_version}*"):
            if candidate != target:
                try:
                    candidate.unlink()
                    removed.append(candidate)
                except OSError:
                    pass
    return removed


def update_workspace() -> Path:
    """Directory used to stage downloads (created on demand)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = base / "HeadSizeStudio" / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def move_into_workspace(source: str | Path, name: str | None = None) -> Path:
    """Move a downloaded payload into the update workspace."""
    source_path = Path(source)
    destination = update_workspace() / (name or source_path.name)
    if source_path.resolve() == destination.resolve():
        return destination
    shutil.move(str(source_path), str(destination))
    return destination


__all__ = [
    "REPLACE_ATTEMPTS",
    "WAIT_SECONDS",
    "SelfUpdateError",
    "apply_update",
    "build_helper_script",
    "cleanup_leftovers",
    "current_executable",
    "move_into_workspace",
    "supports_self_update",
    "update_workspace",
    "write_helper_script",
]
