"""A simple 'who is using this robot right now' lock.

The lock is a small file on the computer that controls the robot, so two
developers on that computer cannot silently overwrite each other's settings.
It does not stop someone on a different computer; agree on booking rules too.

    * Same person re-applying (swapping their own profiles): allowed.
    * Someone else: blocked until the lock is released or expires (8 hours).
    * Use `--force-lock` only after checking with the person named in the lock.
"""
from __future__ import annotations

import getpass
import json
import os
import socket
import time
from pathlib import Path

LOCK_TTL_SECONDS = 8 * 60 * 60


class LockError(Exception):
    pass


def lock_dir() -> Path:
    path = Path(os.environ.get("ROBOT_LOCK_DIR", Path.home() / ".robot_locks"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_user() -> str:
    """Who is acting. Set ROBOT_USER if people share one computer login."""
    return os.environ.get("ROBOT_USER") or getpass.getuser()


def _path(robot: str) -> Path:
    return lock_dir() / f"{robot}.lock"


def status(robot: str):
    """Return the lock's details, or None if the robot is free (or the lock expired)."""
    path = _path(robot)
    if not path.exists():
        return None
    try:
        info = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"user": "unknown (unreadable lock file)", "profile": "?", "host": "?", "expires_at": 0}
    if time.time() > info.get("expires_at", 0):
        return None
    return info


def acquire(robot: str, profile: str, force: bool = False) -> None:
    user = current_user()
    info = status(robot)
    if info and info.get("user") != user and not force:
        left = int((info["expires_at"] - time.time()) / 60)
        raise LockError(
            f"{robot} is in use by {info['user']} (profile '{info.get('profile')}', "
            f"on {info.get('host')}), lock expires in about {left} min. "
            f"Ask them to run `./scripts/rp release {robot}`, or use --force-lock if you have checked with them."
        )
    now = time.time()
    _path(robot).write_text(json.dumps({
        "user": user,
        "profile": profile,
        "host": socket.gethostname(),
        "acquired_at": now,
        "expires_at": now + LOCK_TTL_SECONDS,
    }, indent=2))


def release(robot: str, force: bool = False) -> str:
    info = status(robot)
    path = _path(robot)
    if info is None:
        path.unlink(missing_ok=True)
        return f"{robot} was not locked."
    if info.get("user") != current_user() and not force:
        raise LockError(f"{robot} is locked by {info['user']}. Use --force only after checking with them.")
    path.unlink(missing_ok=True)
    return f"Released {robot} (was held by {info.get('user')})."
