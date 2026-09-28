"""Automated tests. Run from the repo root with:  python3 -m unittest discover -s tests -v

Tests never touch a real robot. They use temporary files and folders.
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from robotprofiles import cli, lock  # noqa: E402
from robotprofiles.adapters.so101 import SO101Adapter, fingerprint  # noqa: E402
from robotprofiles.config import (PROFILES_DIR, ConfigError, check_limits, deep_merge,  # noqa: E402
                                  find_placeholders, list_robots, resolve)
from robotprofiles.wizard import _fill_file  # noqa: E402


class TempProfile:
    """Create a throwaway profile file inside profiles/<robot>/ and delete it afterwards."""

    def __init__(self, robot, name, text):
        self.path = PROFILES_DIR / robot / f"{name}.yaml"
        self.name = name
        self.text = text

    def __enter__(self):
        self.path.write_text(self.text)
        return self

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


class MergeAndPlaceholders(unittest.TestCase):
    def test_dicts_merge_lists_replace(self):
        base = {"a": {"x": 1, "y": 2}, "l": [1, 2, 3]}
        out = deep_merge(base, {"a": {"y": 9}, "l": [7]})
        self.assertEqual(out, {"a": {"x": 1, "y": 9}, "l": [7]})
        self.assertEqual(base["a"]["y"], 2, "the original must not be modified")

    def test_find_placeholders_reports_paths(self):
        found = find_placeholders({"a": {"b": "FILL_ME_IN"}, "c": ["ok", "FILL_ME_IN"], "d": 3})
        self.assertEqual(sorted(found), ["a.b", "c[1]"])


class SafetyLimits(unittest.TestCase):
    LIMITS = {
        "settings.speed": {"min": 0, "max": 0.5},
        "settings.stiff": {"min": 0, "max": [100, 50]},
        "settings.mode": {"allowed": ["a", "b"]},
    }

    def test_within_limits_passes(self):
        v, n, _ = check_limits({"speed": 0.3, "stiff": [90, 10], "mode": "a"}, self.LIMITS)
        self.assertEqual((v, n), ([], []))

    def test_too_high_is_a_violation(self):
        v, _, _ = check_limits({"speed": 0.9}, self.LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("above the maximum", v[0])

    def test_list_limits_are_per_entry(self):
        v, _, _ = check_limits({"stiff": [90, 60]}, self.LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("stiff[1]", v[0])

    def test_wrong_list_length_is_a_violation(self):
        v, _, _ = check_limits({"stiff": [1, 2, 3]}, self.LIMITS)
        self.assertEqual(len(v), 1)

    def test_disallowed_value(self):
        v, _, _ = check_limits({"mode": "effort"}, self.LIMITS)
        self.assertEqual(len(v), 1)

    def test_non_number_is_a_violation_even_with_clamp(self):
        v, _, _ = check_limits({"speed": "fast"}, self.LIMITS, clamp=True)
        self.assertEqual(len(v), 1)

    def test_clamp_forces_values_back(self):
        v, notes, fixed = check_limits({"speed": 0.9, "stiff": [500, 10]}, self.LIMITS, clamp=True)
        self.assertEqual(v, [])
        self.assertEqual(fixed["speed"], 0.5)
        self.assertEqual(fixed["stiff"], [100, 10])
        self.assertEqual(len(notes), 2)

    def test_missing_or_null_settings_are_skipped(self):
        v, _, _ = check_limits({"speed": None}, self.LIMITS)
        self.assertEqual(v, [])


class ResolvingProfiles(unittest.TestCase):
    def test_all_example_profiles_are_valid_in_dry_run(self):
        for robot in list_robots():
            with self.subTest(robot=robot):
                r = resolve(robot, "example_user", allow_placeholders=True)
                self.assertTrue(r.ok, r.errors)

    def test_real_run_refuses_while_values_unknown(self):
        r = resolve("franka", "example_user", allow_placeholders=False)
        self.assertFalse(r.ok)
        self.assertTrue(any("FILL_ME_IN" in e for e in r.errors))

    def test_profile_settings_override_base(self):
        r = resolve("franka", "example_user", allow_placeholders=True)
        self.assertEqual(r.settings["speed_scale"], 0.3)            # from the profile
        self.assertEqual(r.settings["collision"]["torque_threshold_nm"], 20.0)   # inherited from base

    def test_profile_cannot_override_hardware_or_safety(self):
        text = "robot: franka\nprofile: {name: bad, owner: T}\nhardware: {network: {robot_ip: 1.2.3.4}}\nsafety: {limits: {}}\nsettings: {}\n"
        with TempProfile("franka", "_test_bad", text) as p:
            r = resolve("franka", p.name, allow_placeholders=True)
            self.assertFalse(r.ok)
            self.assertTrue(any("forbidden" in e for e in r.errors))

    def test_out_of_range_profile_is_rejected(self):
        text = "robot: franka\nprofile: {name: fast, owner: T}\nsettings: {speed_scale: 0.9}\n"
        with TempProfile("franka", "_test_fast", text) as p:
            r = resolve("franka", p.name, allow_placeholders=True)
            self.assertFalse(r.ok)
            self.assertTrue(any("Safety limit" in e for e in r.errors))

    def test_g1_low_level_mode_is_blocked_by_default(self):
        text = "robot: g1\nprofile: {name: ll, owner: T}\nsettings: {control: {mode: low_level}}\n"
        with TempProfile("g1", "_test_ll", text) as p:
            self.assertFalse(resolve("g1", p.name, allow_placeholders=True).ok)

    def test_wrong_robot_in_profile(self):
        text = "robot: g1\nprofile: {name: x, owner: T}\nsettings: {}\n"
        with TempProfile("franka", "_test_wrong", text) as p:
            self.assertFalse(resolve("franka", p.name, allow_placeholders=True).ok)

    def test_unknown_profile_gives_helpful_error(self):
        with self.assertRaises(ConfigError):
            resolve("franka", "does_not_exist")


class Wizard(unittest.TestCase):
    def test_fills_values_and_keeps_comments(self):
        content = "# top comment\nnetwork:\n  ip: FILL_ME_IN   # the address\nname: FILL_ME_IN\nkeep: 5\n"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "hardware.yaml"
            path.write_text(content)
            answers = iter(["192.168.1.5", ""])   # fill the first, skip the second
            filled = _fill_file(path, ask=lambda _: next(answers), say=lambda *_: None)
            self.assertEqual(filled, 1)
            out = path.read_text()
            self.assertIn("ip: 192.168.1.5   # the address", out)
            self.assertIn("name: FILL_ME_IN", out)
            self.assertIn("# top comment", out)
            self.assertIn("keep: 5", out)

    def test_rejects_invalid_yaml_then_accepts_valid(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "h.yaml"
            path.write_text("val: FILL_ME_IN\n")
            answers = iter(["[unclosed", "[1, 2, 3]"])
            _fill_file(path, ask=lambda _: next(answers), say=lambda *_: None)
            self.assertIn("val: [1, 2, 3]", path.read_text())


class Locking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("ROBOT_LOCK_DIR", "ROBOT_USER")}
        os.environ["ROBOT_LOCK_DIR"] = self.tmp.name

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_other_user_is_blocked_but_owner_can_reapply(self):
        os.environ["ROBOT_USER"] = "alex"
        lock.acquire("franka", "alex_profile")
        lock.acquire("franka", "alex_other_profile")          # same person: fine
        os.environ["ROBOT_USER"] = "sam"
        with self.assertRaises(lock.LockError):
            lock.acquire("franka", "sam_profile")
        lock.acquire("franka", "sam_profile", force=True)       # deliberate takeover
        self.assertEqual(lock.status("franka")["user"], "sam")

    def test_release(self):
        os.environ["ROBOT_USER"] = "alex"
        lock.acquire("g1", "p")
        self.assertIn("Released", lock.release("g1"))
        self.assertIsNone(lock.status("g1"))
        os.environ["ROBOT_USER"] = "sam"
        lock.acquire("g1", "p")
        os.environ["ROBOT_USER"] = "alex"
        with self.assertRaises(lock.LockError):
            lock.release("g1")


class SO101Calibration(unittest.TestCase):
    def _checks(self, hw):
        return dict(((msg, status) for status, msg in SO101Adapter(hw).checks()))

    def test_detects_changed_calibration_file(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "cal.json"
            cal.write_text('{"shoulder_pan": 1}')
            good = fingerprint(cal)
            hw = {"follower": {"port": "FILL_ME_IN", "calibration_file": str(cal), "calibration_sha256": good},
                  "leader": {}}
            statuses = [s for s, m in SO101Adapter(hw).checks() if "follower calibration" in m]
            self.assertEqual(statuses, ["ok"])
            cal.write_text('{"shoulder_pan": 2}')            # someone recalibrated
            statuses = [s for s, m in SO101Adapter(hw).checks() if "follower calibration" in m]
            self.assertEqual(statuses, ["fail"])


class NewProfileCommand(unittest.TestCase):
    def test_new_profile_is_valid_and_refuses_duplicates(self):
        path = PROFILES_DIR / "trossen" / "_test_new.yaml"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["new-profile", "trossen", "_test_new", "--owner", "Tester"]), 0)
                self.assertTrue(path.exists())
                self.assertEqual(cli.main(["validate", "trossen", "_test_new"]), 0)
                self.assertEqual(cli.main(["new-profile", "trossen", "_test_new", "--owner", "Tester"]), 1)
        finally:
            path.unlink(missing_ok=True)

    def test_dry_run_changes_nothing(self):
        active = ROOT / "runtime" / "franka.active.yaml"
        active.unlink(missing_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["apply", "franka", "example_user", "--dry-run"]), 0)
        self.assertFalse(active.exists())

    def test_real_apply_refuses_with_unknown_values(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["apply", "franka", "example_user", "--yes"]), 2)


class GitHook(unittest.TestCase):
    def _git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)

    def test_hardware_change_needs_changelog(self):
        hook = ROOT / "scripts" / "hooks" / "pre-commit"
        with tempfile.TemporaryDirectory() as d:
            self._git(d, "init", "-q")
            self._git(d, "config", "user.email", "t@example.com")
            self._git(d, "config", "user.name", "Tester")
            (Path(d) / "robots" / "franka").mkdir(parents=True)
            (Path(d) / "robots" / "franka" / "hardware.yaml").write_text("a: 1\n")
            self._git(d, "add", "-A")
            blocked = subprocess.run(["sh", str(hook)], cwd=d, capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 1)
            (Path(d) / "robots" / "HARDWARE_CHANGELOG.md").write_text("entry\n")
            self._git(d, "add", "-A")
            allowed = subprocess.run(["sh", str(hook)], cwd=d, capture_output=True, text=True)
            self.assertEqual(allowed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
