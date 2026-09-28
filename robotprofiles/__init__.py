"""robotprofiles: shared, swappable settings profiles for lab robots.

Most people only need one function from this package inside their own robot
control scripts:

    from robotprofiles import load_active
    cfg = load_active("franka")        # the settings applied most recently
    speed = cfg["settings"]["speed_scale"]

Everything else is used through the command line: `./scripts/rp --help`.
"""
from .config import ConfigError, load_active, resolve  # noqa: F401

__all__ = ["ConfigError", "load_active", "resolve"]
