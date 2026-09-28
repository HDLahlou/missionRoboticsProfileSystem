"""Franka arm (FR3 = Franka Research 3, or the older Panda).

Where settings live for this robot:
  * On the robot's control box, edited in the Desk web page or from code: tool
    weight, tool position, and collision-sensitivity thresholds. push() below
    sets them from the profile at every apply, so Desk edits cannot silently drift.
  * In your own control code: controller stiffness, speed, gripper settings.
    Read them with robotprofiles.load_active("franka").

This adapter uses `panda-py`, a community Python wrapper around Franka's libfranka
library. Its API changes between versions, so every vendor call is marked VERIFY.
"""
from __future__ import annotations

from .base import AdapterError, RobotAdapter, is_set, ping


class FrankaAdapter(RobotAdapter):
    robot = "franka"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._panda = None
        self._robot = None

    def checklist(self):
        return [
            "The external activation device (the hand-held emergency stop) is in your hand.",
            "In Desk: the joint brakes are unlocked and FCI (Franka Control Interface) is activated.",
            "The tool on the arm matches the 'tool' section of robots/franka/hardware.yaml.",
            "The area around the arm is clear of people and objects.",
        ]

    def checks(self):
        return [ping(self.hw.get("network", {}).get("robot_ip"))]

    def robot_side_plan(self):
        plan = ["Connect to the arm's control box"]
        if "collision" in self.settings:
            plan.append("Set collision thresholds on the arm from settings.collision")
        plan.append("Set the tool's weight, centre of mass, inertia and tool point from hardware.yaml 'tool'")
        return plan

    def connect(self):
        ip = self.hw.get("network", {}).get("robot_ip")
        if not is_set(ip):
            raise AdapterError("robot_ip is not filled in. Run: ./scripts/rp setup franka")
        try:
            import panda_py  # VERIFY package name and import path
        except ImportError as exc:
            raise AdapterError("panda-py is not installed. Try: pip install panda-py (see its docs)") from exc
        self._panda = panda_py.Panda(ip)            # VERIFY constructor arguments (newer versions may need Desk login details)
        self._robot = self._panda.get_robot()       # VERIFY: low-level libfranka robot object

    def snapshot(self):
        state = self._panda.get_state()             # VERIFY
        return {"joint_positions_rad": [float(q) for q in state.q]}   # VERIFY field name

    def push(self):
        tool = self.hw["tool"]
        collision = self.settings.get("collision")
        if collision:
            t = collision["torque_threshold_nm"]
            f = collision["force_threshold_n"]
            # VERIFY the argument order and count in your panda-py / libfranka version.
            self._robot.set_collision_behavior([t] * 7, [t] * 7, [t] * 7, [t] * 7,
                                               [f] * 6, [f] * 6, [f] * 6, [f] * 6)
        self._robot.set_load(tool["mass_kg"], tool["center_of_mass_m"], tool["inertia_kg_m2"])   # VERIFY
        self._robot.set_EE(tool["flange_to_tcp_transform"])                                      # VERIFY

    def disconnect(self):
        self._panda = None
        self._robot = None
