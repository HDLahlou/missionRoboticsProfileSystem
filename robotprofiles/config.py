"""Loading, layering, and safety-checking of robot configuration files.

How settings are combined ("resolved"), from lowest to highest priority:

    robots/<robot>/base.yaml           shared gentle defaults
    profiles/<robot>/<name>.yaml       one person's or experiment's changes

Hardware facts (robots/<robot>/hardware.yaml) and safety limits
(robots/<robot>/safety.yaml) are loaded READ-ONLY. A profile can never
override them; it can only be checked against them.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# The word written wherever a value is still unknown. Real runs refuse to start
# while any of these remain.
PLACEHOLDER = "FILL_ME_IN"

REPO_ROOT = Path(__file__).resolve().parents[1]
ROBOTS_DIR = REPO_ROOT / "robots"
PROFILES_DIR = REPO_ROOT / "profiles"
RUNTIME_DIR = REPO_ROOT / "runtime"

# The only top-level sections a profile may contain.
ALLOWED_PROFILE_KEYS = {"robot", "profile", "settings"}


class ConfigError(Exception):
    """Raised for problems the user should fix (bad file, unknown robot...)."""


# ----------------------------------------------------------------- file helpers
def list_robots() -> list[str]:
    return sorted(p.name for p in ROBOTS_DIR.iterdir() if p.is_dir())


def list_profiles(robot: str) -> list[str]:
    folder = PROFILES_DIR / robot
    return sorted(p.stem for p in folder.glob("*.yaml")) if folder.is_dir() else []


def read_yaml(path) -> dict:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"File not found: {path}")
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not read {path} (invalid YAML): {exc}") from exc
    return data or {}


def check_robot_name(robot: str) -> None:
    if robot not in list_robots():
        raise ConfigError(f"Unknown robot '{robot}'. Choose one of: {', '.join(list_robots())}")


def profile_path(robot: str, profile: str) -> Path:
    name = profile[:-5] if profile.endswith(".yaml") else profile
    return PROFILES_DIR / robot / f"{name}.yaml"


# ----------------------------------------------------------------- dictionary helpers
def deep_merge(base: dict, override: dict) -> dict:
    """Return base updated with override. Dicts merge; everything else (including
    lists) is replaced wholesale, so a profile's list is never mixed with the base's."""
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def find_placeholders(obj, prefix: str = "") -> list[str]:
    """List the dotted paths of every unknown (FILL_ME_IN) value inside obj."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found += find_placeholders(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found += find_placeholders(value, f"{prefix}[{i}]")
    elif obj == PLACEHOLDER:
        found.append(prefix)
    return found


def get_path(data: dict, dotted: str):
    """Look up 'a.b.c' inside nested dicts. Returns (found, value)."""
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def set_path(data: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    current = data
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


# ----------------------------------------------------------------- safety limit checking
def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _bound_one(value, bound, kind: str, label: str):
    """Check one number against one bound. Returns (new_value, problem, fixable)."""
    if not _is_number(value) or not _is_number(bound):
        return value, f"{label} = {value!r} must be a number", False
    if kind == "max" and value > bound:
        return bound, f"{label} = {value} is above the maximum allowed ({bound})", True
    if kind == "min" and value < bound:
        return bound, f"{label} = {value} is below the minimum allowed ({bound})", True
    return value, None, True


def _apply_bound(path: str, value, bound, kind: str):
    """Check a number or a list of numbers. Returns (new_value, problems, all_fixable)."""
    if isinstance(value, list):
        bounds = bound if isinstance(bound, list) else [bound] * len(value)
        if len(bounds) != len(value):
            return value, [f"{path} has {len(value)} entries but its limit has {len(bounds)}"], False
        new_values, problems, fixable = [], [], True
        for i, (v, b) in enumerate(zip(value, bounds)):
            nv, problem, fix = _bound_one(v, b, kind, f"{path}[{i}]")
            new_values.append(nv)
            if problem:
                problems.append(problem)
                fixable = fixable and fix
        return new_values, problems, fixable
    if isinstance(bound, list):
        return value, [f"{path} is a single value but its limit is a list"], False
    new_value, problem, fix = _bound_one(value, bound, kind, path)
    return new_value, ([problem] if problem else []), fix


def check_limits(settings: dict, limits: dict, clamp: bool = False):
    """Compare settings with the safety rules.

    Returns (violations, clamped_notes, new_settings).
      * violations: problems that stop the run.
      * clamped_notes: values that were forced back to the limit (only with clamp=True).
    Rules whose setting is absent or null are skipped.
    """
    violations: list[str] = []
    notes: list[str] = []
    wrapper = {"settings": copy.deepcopy(settings)}

    for path, rule in (limits or {}).items():
        found, value = get_path(wrapper, path)
        if not found or value is None:
            continue

        if "allowed" in rule and value not in rule["allowed"]:
            violations.append(f"{path} = {value!r} is not one of the allowed values {rule['allowed']}")
            continue

        for kind in ("min", "max"):
            if kind not in rule:
                continue
            new_value, problems, fixable = _apply_bound(path, value, rule[kind], kind)
            if not problems:
                continue
            if clamp and fixable:
                set_path(wrapper, path, new_value)
                value = new_value
                notes.extend(f"CLAMPED: {p}" for p in problems)
            else:
                # The same problem (e.g. "not a number") can show up for both min and max.
                violations.extend(p for p in problems if p not in violations)

    return violations, notes, wrapper["settings"]


# ----------------------------------------------------------------- resolving a profile
@dataclass
class Resolved:
    robot: str
    profile_name: str
    hardware: dict
    safety: dict
    settings: dict
    profile_meta: dict
    files: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    clamped: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            raise ConfigError("\n".join(f"  - {e}" for e in self.errors))

    def active_document(self) -> dict:
        """What gets written for your control scripts to read."""
        return {
            "robot": self.robot,
            "profile": self.profile_name,
            "owner": self.profile_meta.get("owner"),
            "settings": self.settings,
        }


def load_hardware(robot: str) -> dict:
    check_robot_name(robot)
    return read_yaml(ROBOTS_DIR / robot / "hardware.yaml")


def resolve(robot: str, profile: str, allow_placeholders: bool = False, clamp: bool = False) -> Resolved:
    """Combine hardware, safety, base, and a profile, then check everything.

    allow_placeholders=True (used for dry runs and validation) turns 'value still
    unknown' errors into warnings. Safety-limit violations are ALWAYS errors.
    """
    check_robot_name(robot)
    hw_file = ROBOTS_DIR / robot / "hardware.yaml"
    sf_file = ROBOTS_DIR / robot / "safety.yaml"
    base_file = ROBOTS_DIR / robot / "base.yaml"
    prof_file = profile_path(robot, profile)

    hardware = read_yaml(hw_file)
    safety = read_yaml(sf_file)
    base = read_yaml(base_file)
    if not prof_file.exists():
        available = ", ".join(list_profiles(robot)) or "(none yet)"
        raise ConfigError(
            f"Profile '{profile}' not found for {robot}. Available: {available}. "
            f"Create one with: ./scripts/rp new-profile {robot} <name>"
        )
    prof = read_yaml(prof_file)

    result = Resolved(
        robot=robot,
        profile_name=prof_file.stem,
        hardware=hardware,
        safety=safety,
        settings={},
        profile_meta=prof.get("profile") or {},
        files=[str(p.relative_to(REPO_ROOT)) for p in (hw_file, sf_file, base_file, prof_file)],
    )

    # 1. A profile may only contain robot / profile / settings.
    extra = sorted(set(prof) - ALLOWED_PROFILE_KEYS)
    if extra:
        result.errors.append(
            f"Profile contains forbidden section(s) {extra}. Profiles may only contain "
            f"{sorted(ALLOWED_PROFILE_KEYS)}. Hardware facts and safety limits are shared "
            f"and cannot be overridden from a profile."
        )
    if prof.get("robot") != robot:
        result.errors.append(f"Profile says robot: {prof.get('robot')!r} but you asked for {robot!r}.")

    # 2. Layer the settings.
    result.settings = deep_merge(base.get("settings") or {}, prof.get("settings") or {})

    # 3. Unknown values.
    unknown = []
    for label, doc in (("hardware", hardware), ("safety", safety), ("base", base), ("profile", prof)):
        unknown += [f"{label}: {p}" for p in find_placeholders(doc)]
    if unknown:
        message = (
            f"{len(unknown)} value(s) still marked {PLACEHOLDER}: " + "; ".join(unknown[:6])
            + (" ..." if len(unknown) > 6 else "")
            + f". Run `./scripts/rp setup {robot}` to fill in hardware/safety values."
        )
        (result.warnings if allow_placeholders else result.errors).append(message)

    # 4. Safety limits (always enforced).
    violations, notes, checked = check_limits(result.settings, safety.get("limits"), clamp=clamp)
    result.settings = checked
    result.clamped = notes
    result.errors.extend(f"Safety limit: {v}" for v in violations)

    return result


def load_active(robot: str) -> dict:
    """Read the settings most recently applied for this robot.

    Call this at the top of your own control scripts instead of hard-coding numbers.
    """
    path = RUNTIME_DIR / f"{robot}.active.yaml"
    if not path.exists():
        raise ConfigError(
            f"No active profile for '{robot}' yet. Apply one first: ./scripts/rp apply {robot} <profile>"
        )
    return read_yaml(path)
