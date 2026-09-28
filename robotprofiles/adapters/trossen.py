"""Trossen Robotics arm (newer Trossen AI arms, `trossen_arm` driver).

Where settings live for this robot: mostly in your own control code (which mode
to use, how long each move takes, stiffness scaling), read from the active file
with robotprofiles.load_active("trossen"). Older WidowX / ViperX arms (Dynamixel
motors, Interbotix software) use a different library and need a different
adapter. TODO (needs your input): tell us which generation you have.

Vendor calls are marked VERIFY.
"""
from __future__ import annotations

from .base import AdapterError, RobotAdapter, is_set, ping


class TrossenAdapter(RobotAdapter):
    robot = "trossen"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._driver = None

    def checklist(self):
        return [
            "The arm is powered and its emergency stop or power switch is within reach.",
            "The end effector (gripper) fitted matches hardware.yaml.",
            "This arm's role (leader or follower) matches what you intend.",
            "The area around the arm is clear.",
        ]

    def checks(self):
        return [ping(self.hw.get("network", {}).get("ip_address"))]

    def robot_side_plan(self):
        return ["Connect and configure the arm with the driver using hardware.yaml (model, end effector, IP address)",
                "Your own control code applies mode, goal time and gains from the active file"]

    def connect(self):
        needed = {k: self.hw.get(k) for k in ("model", "end_effector")}
        ip = self.hw.get("network", {}).get("ip_address")
        missing = [k for k, v in needed.items() if not is_set(v)] + ([] if is_set(ip) else ["network.ip_address"])
        if missing:
            raise AdapterError(f"Not filled in: {', '.join(missing)}. Run: ./scripts/rp setup trossen")
        try:
            import trossen_arm  # VERIFY package name
        except ImportError as exc:
            raise AdapterError("The trossen_arm package is not installed. See Trossen's documentation.") from exc
        model = getattr(trossen_arm.Model, needed["model"])                          # VERIFY enum names
        effector = getattr(trossen_arm.StandardEndEffector, needed["end_effector"])  # VERIFY enum names
        self._driver = trossen_arm.TrossenArmDriver()                                # VERIFY
        self._driver.configure(model, effector, ip, True)                            # VERIFY argument list

    def snapshot(self):
        return {"joint_positions": [float(x) for x in self._driver.get_all_positions()]}   # VERIFY method name

    def disconnect(self):
        self._driver = None
