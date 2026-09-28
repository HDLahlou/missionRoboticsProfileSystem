"""SO-101 leader and follower arms (LeRobot).

Where settings live for this robot:
  * Calibration files on the computer (managed by LeRobot). Treated as a SHARED
    HARDWARE FACT: this adapter compares each file's fingerprint (SHA-256) with
    the one recorded in hardware.yaml and warns if someone has recalibrated.
  * Motor-level values (stiffness, step size): read from the active file by your
    own recording or control code.

LeRobot opens the USB connection itself inside your scripts, so connect() and
push() do nothing here. To push motor settings straight to the servos instead,
add code to push() using LeRobot's motor-bus classes (TODO, VERIFY the API for
your installed version).
"""
from __future__ import annotations

import hashlib
import os

from .base import RobotAdapter, is_set


def fingerprint(path) -> str | None:
    """SHA-256 fingerprint of a file: any change to the file changes this value."""
    path = os.path.expanduser(str(path))
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class SO101Adapter(RobotAdapter):
    robot = "so101"
    ARMS = ("follower", "leader")

    def checklist(self):
        return [
            "Both arms are plugged in by USB and the follower's power supply is on.",
            "Nobody is recalibrating or re-flashing the arms right now.",
            "The follower's workspace is clear (it will move when you start teleoperating).",
            "You know how to cut power quickly (unplug the follower's power supply).",
        ]

    def checks(self):
        results = []
        for arm in self.ARMS:
            info = self.hw.get(arm, {})
            port = info.get("port")
            if is_set(port):
                results.append(("ok" if os.path.exists(str(port)) else "fail",
                                f"{arm} port {port} " + ("exists" if os.path.exists(str(port)) else "was not found")))
            else:
                results.append(("warn", f"{arm}.port not filled in yet"))

            cal = info.get("calibration_file")
            recorded = info.get("calibration_sha256")
            if not is_set(cal):
                results.append(("warn", f"{arm}.calibration_file not filled in yet"))
                continue
            actual = fingerprint(cal)
            if actual is None:
                results.append(("fail", f"{arm} calibration file not found: {cal}"))
            elif not is_set(recorded):
                results.append(("warn", f"{arm} calibration fingerprint not recorded yet. Current value: {actual}"))
            elif actual != recorded:
                results.append(("fail", f"{arm} calibration file CHANGED since it was recorded. Data and policies "
                                        f"made earlier may not line up. If the recalibration was intended, update "
                                        f"hardware.yaml (new fingerprint {actual}) and log it in the changelog."))
            else:
                results.append(("ok", f"{arm} calibration fingerprint matches"))
        return results

    def robot_side_plan(self):
        return ["Compare calibration fingerprints with hardware.yaml",
                "Your own LeRobot scripts read motor settings from the active file (nothing is sent to the servos here)"]

    def snapshot(self):
        out = {}
        for arm in self.ARMS:
            cal = self.hw.get(arm, {}).get("calibration_file")
            out[f"{arm}_calibration_sha256"] = fingerprint(cal) if is_set(cal) else None
        return out
