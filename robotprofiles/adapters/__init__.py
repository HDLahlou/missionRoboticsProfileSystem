"""One adapter per robot. Add a new robot by adding a folder under robots/, a file here,
and one line below."""
from ..config import ConfigError
from .franka import FrankaAdapter
from .g1 import G1Adapter
from .so101 import SO101Adapter
from .trossen import TrossenAdapter

ADAPTERS = {a.robot: a for a in (FrankaAdapter, G1Adapter, SO101Adapter, TrossenAdapter)}


def get_adapter(robot: str):
    try:
        return ADAPTERS[robot]
    except KeyError:
        raise ConfigError(f"No adapter written for robot '{robot}'. Known: {', '.join(ADAPTERS)}") from None
