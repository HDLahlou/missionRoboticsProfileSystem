"""Write a record of every real apply, so results can be traced to exact settings."""
from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path

from .config import REPO_ROOT
from .lock import current_user

RUNS_DIR = REPO_ROOT / "runs"


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def git_info() -> dict:
    """Which version of these config files was used? 'dirty' means edited but not committed."""
    return {"commit": _git("rev-parse", "HEAD") or "unknown (not a git repository?)",
            "dirty": bool(_git("status", "--porcelain"))}


def write_run_log(resolved, before, after) -> Path:
    RUNS_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = RUNS_DIR / f"{stamp}_{resolved.robot}_{resolved.profile_name}.json"
    path.write_text(json.dumps({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user": current_user(),
        "host": socket.gethostname(),
        "robot": resolved.robot,
        "profile": resolved.profile_name,
        "git": git_info(),
        "files_used": resolved.files,
        "clamped": resolved.clamped,
        "settings": resolved.settings,
        "robot_state_before": before,
        "robot_state_after": after,
    }, indent=2, default=str))
    return path
