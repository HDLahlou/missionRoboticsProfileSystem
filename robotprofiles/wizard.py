"""Interactive helper that fills in unknown (FILL_ME_IN) values.

It edits the file as plain text, one line at a time, so all the explanatory
comments in hardware.yaml and safety.yaml are preserved.
"""
from __future__ import annotations

import re

import yaml

from .config import PLACEHOLDER, ROBOTS_DIR, check_robot_name

LINE = re.compile(r"^(\s*)([A-Za-z0-9_\-]+):\s*(.*)$")


def _fill_file(path, ask=input, say=print) -> int:
    lines = path.read_text().splitlines(keepends=True)
    stack: list[tuple[int, str]] = []   # (indent, key) to build the full 'a.b.c' path
    recent_comments: list[str] = []
    filled = 0

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#"):
            recent_comments.append(stripped.lstrip("# ").rstrip())
            continue
        match = LINE.match(raw.rstrip("\n"))
        if not stripped or not match:
            recent_comments = []
            continue

        indent, key, rest = len(match.group(1)), match.group(2), match.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))

        if rest.startswith(PLACEHOLDER):
            inline = rest[len(PLACEHOLDER):].strip().lstrip("# ").strip()
            dotted = ".".join(k for _, k in stack)
            say(f"\n{path.name}: {dotted}")
            for note in recent_comments[-2:]:
                say(f"    {note}")
            if inline:
                say(f"    {inline}")
            while True:
                answer = ask("  value (Enter to skip): ").strip()
                if not answer:
                    break
                try:
                    yaml.safe_load(answer)
                except yaml.YAMLError:
                    say("  That is not valid YAML. Text with special characters needs quotes, e.g. \"my value\".")
                    continue
                suffix = f"   # {inline}" if inline else ""
                lines[i] = f"{match.group(1)}{key}: {answer}{suffix}\n"
                filled += 1
                break
        recent_comments = []

    if filled:
        path.write_text("".join(lines))
    return filled


def run_setup(robot: str, ask=input, say=print) -> None:
    check_robot_name(robot)
    say(f"Setting up {robot}. You will be asked for each unknown value.")
    say("Press Enter to skip any value you do not know yet; you can run this again later.")
    total = 0
    for name in ("hardware.yaml", "safety.yaml"):
        total += _fill_file(ROBOTS_DIR / robot / name, ask=ask, say=say)
    say(f"\nFilled in {total} value(s).")
    if total:
        say("Next steps (these files are protected on purpose):")
        say("  1. Add a line to robots/HARDWARE_CHANGELOG.md describing what you filled in and why.")
        say("  2. Have a second person review the change, then commit it.")
