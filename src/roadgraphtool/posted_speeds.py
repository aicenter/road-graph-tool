"""Posted speed mapping for the graph contraction with posted speeds (``contraction.speed_source: posted``)."""

import copy
from typing import Any, Dict

# Czech defaults for urban areas, source: https://wiki.openstreetmap.org/wiki/Default_speed_limits
# The highway defaults apply to ways without a usable maxspeed tag; the whole area is assumed to be urban.
DEFAULT_POSTED_SPEEDS: Dict[str, Any] = {
    "default": 50,
    "highway": {
        "motorway": 80,
        "motorway_link": 80,
        "trunk": 80,
        "trunk_link": 80,
        "living_street": 20,
    },
    "zones": {
        "CZ:urban": 50,
        "CZ:rural": 90,
        "CZ:trunk": 110,
        "CZ:motorway": 130,
        "CZ:living_street": 20,
        "CZ:pedestrian_zone": 20,
    },
}


def _to_dict(value) -> Dict[str, Any]:
    return value if isinstance(value, dict) else vars(value)


def _check_speed(name: str, speed) -> None:
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or speed <= 0:
        raise ValueError(f"contraction.posted_speeds: {name} must be a positive number (km/h), got {speed!r}")


def get_posted_speeds(config) -> Dict[str, Any]:
    """Built-in posted speed mapping updated by ``contraction.posted_speeds`` from the config.

    ``default`` replaces the default speed, the ``highway`` and ``zones`` entries are merged into the built-in ones.
    """
    posted_speeds = copy.deepcopy(DEFAULT_POSTED_SPEEDS)
    overrides = getattr(config.contraction, "posted_speeds", None)
    if overrides is not None:
        overrides = _to_dict(overrides)
        unknown_keys = set(overrides) - set(posted_speeds)
        if unknown_keys:
            raise ValueError(f"contraction.posted_speeds: unknown keys {sorted(unknown_keys)}")
        if "default" in overrides:
            posted_speeds["default"] = overrides["default"]
        for key in ("highway", "zones"):
            if key in overrides:
                posted_speeds[key].update(_to_dict(overrides[key]))

    _check_speed("default", posted_speeds["default"])
    for key in ("highway", "zones"):
        for name, speed in posted_speeds[key].items():
            _check_speed(f"{key}.{name}", speed)
    return posted_speeds
