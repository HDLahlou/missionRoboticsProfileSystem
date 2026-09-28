"""Unitree G1 humanoid (EDU model).

Where settings live for this robot: almost entirely in YOUR control code. Joint
stiffness and damping gains are sent to the robot many times per second by your
own program, and locomotion speed limits are passed with your movement commands.
So this adapter mainly (a) checks the connection and (b) publishes the active
settings file for your code to read with robotprofiles.load_active("g1").

Communication uses DDS (Data Distribution Service) through Unitree's
`unitree_sdk2_python`. Vendor calls are marked VERIFY.
"""
from __future__ import annotations

import socket

from .base import AdapterError, RobotAdapter, is_set, ping


class G1Adapter(RobotAdapter):
    robot = "g1"

    def checklist(self):
        return [
            "The robot is hanging from the gantry or harness (a hoist that catches it if it falls). "
            "REQUIRED for any new settings.",
            "You can trigger emergency damping / a stop from the remote controller.",
            "There is at least 2 metres of clear space around the robot.",
            "Someone else in the room knows you are about to start.",
            "You are using high-level control. Low-level control needs a documented safety review.",
        ]

    def checks(self):
        results = []
        iface = self.hw.get("network", {}).get("interface")
        if not is_set(iface):
            results.append(("warn", "network.interface not filled in yet, so the cable connection was not checked"))
        else:
            names = [name for _, name in socket.if_nameindex()]
            if iface in names:
                results.append(("ok", f"Network interface {iface} exists on this computer"))
            else:
                results.append(("fail", f"Network interface {iface} not found. Found: {', '.join(names)}"))
        results.append(ping(self.hw.get("network", {}).get("robot_ip")))
        return results

    def robot_side_plan(self):
        return ["Start the DDS connection on the named network interface (the robot receives nothing yet)",
                "Your own control code applies gains and speed limits from the active file"]

    def connect(self):
        iface = self.hw.get("network", {}).get("interface")
        if not is_set(iface):
            raise AdapterError("network.interface is not filled in. Run: ./scripts/rp setup g1")
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize  # VERIFY import path
        except ImportError as exc:
            raise AdapterError("unitree_sdk2_python is not installed. See Unitree's GitHub instructions.") from exc
        ChannelFactoryInitialize(0, iface)   # VERIFY: (domain id, network interface name)

    def snapshot(self):
        # TODO (needs your input): read the robot's state by subscribing to its low-state
        # message with the SDK, then return joint angles here. Left empty on purpose so
        # nothing is guessed. Example return value: {"joint_positions_rad": [...]}
        return {"note": "G1 state readback not implemented yet (see TODO in adapters/g1.py)"}
