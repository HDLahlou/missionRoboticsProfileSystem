"""Command-line interface. Run `./scripts/rp --help` for the list of commands."""
from __future__ import annotations

import argparse
import re
import time

import yaml

from . import lock, runlog
from .adapters import get_adapter
from .adapters.base import AdapterError
from .config import (PROFILES_DIR, ROBOTS_DIR, ConfigError, check_robot_name, list_profiles,
                     list_robots, load_hardware, profile_path, read_yaml, resolve)
from .wizard import run_setup

NAME_OK = re.compile(r"^[A-Za-z0-9_\-]+$")


def ask_yes(question: str) -> bool:
    return input(f"  [ ] {question}  (y/N) ").strip().lower() in ("y", "yes")


# ------------------------------------------------------------------ commands
def cmd_list(args) -> int:
    for robot in list_robots():
        info = lock.status(robot)
        held = f"IN USE by {info['user']} ({info.get('profile')})" if info else "free"
        print(f"{robot}  [{held}]")
        for name in list_profiles(robot):
            print(f"    - {name}")
    return 0


def cmd_setup(args) -> int:
    run_setup(args.robot)
    return 0


def cmd_new_profile(args) -> int:
    check_robot_name(args.robot)
    if not NAME_OK.match(args.name):
        raise ConfigError("Profile names may only contain letters, numbers, underscores and hyphens.")
    target = profile_path(args.robot, args.name)
    if target.exists():
        raise ConfigError(f"{target} already exists. Choose another name or edit that file.")
    owner = args.owner or input(f"Your name [{lock.current_user()}]: ").strip() or lock.current_user()

    text = (PROFILES_DIR / "_template.yaml").read_text()
    text = text.replace("ROBOT_NAME", args.robot).replace("PROFILE_NAME", args.name).replace("OWNER_NAME", owner)
    base = read_yaml(ROBOTS_DIR / args.robot / "base.yaml").get("settings") or {}
    reference = "\n".join("  # " + line for line in yaml.safe_dump(base, sort_keys=False).splitlines())
    text = (text.rstrip("\n") + "\n  # Shared defaults you can override. To change one, copy the line, remove the '# '\n"
            "  # and set your value (keep the same indentation):\n" + reference + "\n")
    target.parent.mkdir(exist_ok=True)
    target.write_text(text)
    print(f"Created {target.relative_to(PROFILES_DIR.parent)}")
    print("Edit it, then check it with:  ./scripts/rp validate " f"{args.robot} {args.name}")
    return 0


def _print_messages(resolved) -> None:
    for w in resolved.warnings:
        print(f"Warning: {w}")
    for n in resolved.clamped:
        print(n)
    for e in resolved.errors:
        print(f"ERROR: {e}")


def cmd_validate(args) -> int:
    resolved = resolve(args.robot, args.profile, allow_placeholders=True, clamp=args.clamp)
    _print_messages(resolved)
    if resolved.ok:
        print(f"OK: profile '{resolved.profile_name}' is valid for {args.robot}.")
        return 0
    return 2


def cmd_apply(args) -> int:
    resolved = resolve(args.robot, args.profile, allow_placeholders=args.dry_run, clamp=args.clamp)
    _print_messages(resolved)
    if not resolved.ok:
        print("\nNothing was changed.")
        return 2

    adapter = get_adapter(args.robot)(resolved.hardware, resolved, dry_run=args.dry_run)
    print(f"\nPlan for {args.robot} with profile '{resolved.profile_name}':")
    for step in adapter.plan():
        print(f"  - {step}")
    print("\nSettings that will be applied:")
    print(yaml.safe_dump(resolved.settings, sort_keys=False))

    if args.dry_run:
        print("Dry run: nothing was changed.")
        return 0

    # 1. Automatic checks.
    failed = False
    print("Automatic checks:")
    for status, message in adapter.checks():
        print(f"  [{status.upper():4}] {message}")
        failed = failed or status == "fail"
    if failed:
        print("\nA check failed. Nothing was changed.")
        return 3

    # 2. Human checklist.
    if not args.yes:
        print("\nConfirm each item (answer y):")
        for question in adapter.checklist():
            if not ask_yes(question):
                print("\nStopped. Nothing was changed.")
                return 3

    # 3. Lock, connect, apply, log.
    was_locked = lock.status(args.robot) is not None
    lock.acquire(args.robot, resolved.profile_name, force=args.force_lock)
    before = after = {}
    try:
        adapter.connect()
        before = adapter.snapshot()
        adapter.apply()
        after = adapter.snapshot()
    except AdapterError:
        if not was_locked:
            lock.release(args.robot, force=True)
        raise
    finally:
        adapter.disconnect()

    log = runlog.write_run_log(resolved, before, after)
    print(f"\nApplied '{resolved.profile_name}' to {args.robot}.")
    print(f"Your control scripts can now call: robotprofiles.load_active('{args.robot}')")
    print(f"Run log: {log}")
    print(f"When you finish, free the robot with: ./scripts/rp release {args.robot}")
    return 0


def cmd_snapshot(args) -> int:
    check_robot_name(args.robot)
    adapter = get_adapter(args.robot)(load_hardware(args.robot))
    for status, message in adapter.checks():
        print(f"[{status.upper():4}] {message}")
    adapter.connect()
    try:
        print(yaml.safe_dump(adapter.snapshot(), sort_keys=False))
    finally:
        adapter.disconnect()
    return 0


def cmd_status(args) -> int:
    robots = [args.robot] if args.robot else list_robots()
    for robot in robots:
        check_robot_name(robot)
        info = lock.status(robot)
        if not info:
            print(f"{robot}: free")
        else:
            left = int((info["expires_at"] - time.time()) / 60)
            print(f"{robot}: in use by {info['user']} on {info.get('host')} with profile "
                  f"'{info.get('profile')}' (lock expires in ~{left} min)")
    return 0


def cmd_release(args) -> int:
    check_robot_name(args.robot)
    print(lock.release(args.robot, force=args.force))
    return 0


# ------------------------------------------------------------------ wiring
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rp", description="Swap and preserve robot settings profiles.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("list", help="show robots, their profiles, and who is using them")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("setup", help="fill in unknown hardware/safety values, one prompt at a time")
    s.add_argument("robot")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("new-profile", help="create your own profile from the template")
    s.add_argument("robot")
    s.add_argument("name")
    s.add_argument("--owner", help="your name (asked if omitted)")
    s.set_defaults(func=cmd_new_profile)

    s = sub.add_parser("validate", help="check a profile against the safety limits")
    s.add_argument("robot")
    s.add_argument("profile")
    s.add_argument("--clamp", action="store_true", help="force out-of-range values back to the limit")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("apply", help="apply a profile to a robot")
    s.add_argument("robot")
    s.add_argument("profile")
    s.add_argument("--dry-run", action="store_true", help="show the plan; touch nothing")
    s.add_argument("--clamp", action="store_true", help="force out-of-range values back to the limit")
    s.add_argument("--yes", action="store_true", help="skip the human checklist (automatic checks still run)")
    s.add_argument("--force-lock", action="store_true", help="take over a lock held by someone else")
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("snapshot", help="read the robot's current state (SO-101: calibration fingerprints)")
    s.add_argument("robot")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("status", help="show who holds each robot's lock")
    s.add_argument("robot", nargs="?")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("release", help="free the robot when you are done")
    s.add_argument("robot")
    s.add_argument("--force", action="store_true", help="release a lock held by someone else")
    s.set_defaults(func=cmd_release)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, lock.LockError, AdapterError) as exc:
        print(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
