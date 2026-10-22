"""Unified road network import: OSM file (osm2pgsql) or Overpass API."""

from __future__ import annotations

import json
from typing import Optional

import shapely.geometry as geometry
from shapely.geometry import shape

from roadgraphtool.db import db
from roadgraphtool.exceptions import MissingInputError
from roadgraphtool.overpass_client import _read_nested

NETWORK_PROFILES = ("car", "pedestrian")
"""Supported values of ``road_import.profile``. The profile selects which ways are imported and how their
direction is interpreted."""

# Built-in osm2pgsql style matching each profile. A custom ``.lua`` path is accepted for any profile.
_PROFILE_BUILTIN_STYLES = {"car": "pipeline", "pedestrian": "pedestrian"}


def get_network_profile(config) -> str:
    """Return ``road_import.profile`` (default ``car``). Raises ``ValueError`` for unknown profiles."""
    profile = _read_nested(config, "road_import.profile", None)
    if profile is None:
        return "car"
    if profile not in NETWORK_PROFILES:
        raise ValueError(
            f"Unknown road_import.profile: {profile!r}. Must be one of: {', '.join(NETWORK_PROFILES)}."
        )
    return profile


def check_style_matches_profile(profile: str, style_file: str) -> None:
    """Reject a built-in osm2pgsql style that belongs to a different profile than *profile*.

    Custom ``.lua`` styles are not checked.
    """
    style_file = str(style_file)
    if style_file.endswith(".lua"):
        return
    for other_profile, builtin_style in _PROFILE_BUILTIN_STYLES.items():
        if style_file == builtin_style and other_profile != profile:
            raise ValueError(
                f"road_import.source.style_file {style_file!r} is the built-in style for the "
                f"{other_profile!r} profile, but road_import.profile is {profile!r}. Use style "
                f"{_PROFILE_BUILTIN_STYLES[profile]!r} or a custom .lua style."
            )


def get_area_polygon(config, area_id: int) -> Optional[geometry.base.BaseGeometry]:
    """Load area geometry from ``areas`` in *config.schema*. Returns None if missing."""
    target_schema = config.schema
    rows = db.execute_sql_and_fetch_all_rows(
        f'SELECT ST_AsGeoJSON(geom) FROM "{target_schema}".areas WHERE id = {int(area_id)}'
    )
    if not rows or rows[0][0] is None:
        return None
    gj = rows[0][0]
    if isinstance(gj, str):
        return shape(json.loads(gj))
    return shape(gj)


def import_road_network(config, area_id: Optional[int]) -> int:
    """
    Run exactly one road import backend based on ``config.road_import.source.type``.

    Returns the area id associated with imported graph data (existing area when
    filtering, or newly created area for OSM file import without *area_id*).
    """
    if not hasattr(config, "road_import"):
        raise ValueError("road_import section missing from configuration.")

    ri = config.road_import
    if not hasattr(ri, "source"):
        raise ValueError(
            "road_import.source not specified. Add road_import.source with a "
            "'type' field (osm_file or overpass)."
        )
    source = ri.source
    if not hasattr(source, "type"):
        raise ValueError(
            "road_import.source.type not specified. Must be one of: osm_file, overpass."
        )

    profile = get_network_profile(config)

    src_type = source.type
    if src_type == "overpass":
        if area_id is None:
            raise MissingInputError(
                "road_import with source.type overpass requires an area id. "
                "Enable area_insert, set root area_id, or run a prior step that sets area_id."
            )
        poly = get_area_polygon(config, area_id)
        if poly is None:
            raise ValueError(
                f"No geometry found for area id {area_id} in schema {config.schema}.areas."
            )
        from roadgraphtool.overpass_import import _run_overpass_backend

        return _run_overpass_backend(config, area_id, poly)

    if src_type == "osm_file":
        if not hasattr(source, "input_file"):
            raise ValueError(
                "road_import.source.input_file not specified for source.type osm_file."
            )
        check_style_matches_profile(profile, source.style_file)
        from roadgraphtool.process_osm import _run_osm_file_backend

        return _run_osm_file_backend(config, area_id)

    raise ValueError(
        f"Unknown road_import.source.type: {src_type!r}. Must be osm_file or overpass."
    )
