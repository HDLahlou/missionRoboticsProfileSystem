"""Common structure for the four robot adapters.

An ADAPTER is the small piece of code that knows how to talk to one specific
robot. The rest of the tool (loading profiles, checking safety limits, locking,
logging) is identical for every robot; only the adapters differ.

Every adapter follows the same steps when you apply a profile:

    1. checks()      automatic checks (is the robot reachable? are files present?)
    2. checklist()   yes/no questions only a human can answer (is the e-stop in reach?)
    3. connect()     open a connection to the robot
    4. snapshot()    read the robot's current state (before)
    5. apply()       write runtime/<robot>.active.yaml, then push() settings to the robot
    6. snapshot()    read the state again (after)
    7. disconnect()

IMPORTANT: vendor libraries change often. Every line that calls one is marked
`# VERIFY`; check it against the current vendor documentation before trusting it.
"""
from __future__ import annotations

import subprocess
import sys

import yaml

from ..config import PLACEHOLDER, RUNTIME_DIR, Resolved


class AdapterError(Exception):
    """A problem talking to the robot that the user can act on."""


def is_set(value) -> bool:
    """True when a hardware value has been filled in (is not None or FILL_ME_IN)."""
    return value is not None and value != PLACEHOLDER


def ping(host) -> tuple[str, str]:
    """Check that a network address answers. Returns (status, message)."""
    if not is_set(host):
        return "warn", "IP address not filled in yet, so reachability was not checked"
    try:
        count_flag = "-n" if sys.platform.startswith("win") else "-c"   # Windows uses -n
        result = subprocess.run(["ping", count_flag, "1", str(host)], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "warn", f"Could not run ping for {host} (ping missing or timed out)"
    if result.returncode == 0:
        return "ok", f"{host} answers ping"
    return "fail", f"{host} does not answer ping. Check power, cable, and network settings."


class RobotAdapter:
    robot = "base"

    def __init__(self, hardware: dict, resolved: Resolved | None = None, dry_run: bool = False):
        self.hw = hardware
        self.resolved = resolved
        self.settings = resolved.settings if resolved else {}
        self.dry_run = dry_run

    # ---- things a person must confirm (override per robot)
    def checklist(self) -> list[str]:
        return ["The emergency stop is within reach.", "The area around the robot is clear."]

    # ---- automatic checks (override per robot). Each returns (status, message).
    def checks(self) -> list[tuple[str, str]]:
        return []

    # ---- describe what apply() would do, without touching anything
    def robot_side_plan(self) -> list[str]:
        return []

    def plan(self) -> list[str]:
        steps = [f"Write runtime/{self.robot}.active.yaml so your control scripts can read the settings"]
        return steps + self.robot_side_plan()

    # ---- connection lifecycle (override per robot)
    def connect(self) -> None:
        pass

    def snapshot(self) -> dict:
        return {}

    def push(self) -> None:
        """Send settings to the robot itself. Most settings are simply read by your
        own control code from the active file, so many adapters do little here."""

    def disconnect(self) -> None:
        pass

    # ---- shared
    def write_active_file(self):
        RUNTIME_DIR.mkdir(exist_ok=True)
        path = RUNTIME_DIR / f"{self.robot}.active.yaml"
        header = "# Written by robotprofiles. Do not edit by hand; run `./scripts/rp apply` instead.\n"
        path.write_text(header + yaml.safe_dump(self.resolved.active_document(), sort_keys=False))
        return path

    def apply(self):
        path = self.write_active_file()
        self.push()
        return path
