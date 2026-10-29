import yaml
import os.path
import logging
import pandas as pd
from typing import Any, Dict, Optional
import geopandas as gpd
from pathlib import Path

import roadgraphtool.exec
from roadgraphtool.overpass_client import _read_nested

DM_OUTPUT_FORMATS = ("csv", "hdf")

# extensions appended by shortestPathsPreprocessor to its output path
_DM_TOOL_EXTENSIONS = {"csv": ".csv", "hdf": ".hdf5"}


def _set_config_defaults(config: Dict, defaults: Dict):
    for key, val in defaults.items():
        if isinstance(val, dict):
            _set_config_defaults(config[key], defaults[key])
        else:
            if key not in config:
                config[key] = defaults[key]


def load_instance_config(config_file_path: Path) -> Dict:
    config_file_path_abs = config_file_path.absolute()
    logging.info(f"Loading instance config from {config_file_path_abs}")
    with open(config_file_path_abs, 'r') as config_file:
        try:
            config = yaml.safe_load(config_file)

            defaults = {
                'instance_dir': os.path.dirname(config_file_path),
                'map': {'path': config_file_path.parent / 'map'},
                'demand': {'type': 'generate', 'min_time': 0, 'max_time': 86_400  # 24:00
                },
                'vehicles': {'start_time': config['demand']['min_time']}}

            _set_config_defaults(config, defaults)
            return config
        except yaml.YAMLError as er:
            logging.error(er)


def _normalize_dm_output_format(output_format: str) -> str:
    normalized = output_format.lower()
    if normalized not in DM_OUTPUT_FORMATS:
        raise ValueError(
            f"Unsupported dm output format {output_format!r}; "
            f"expected one of {', '.join(DM_OUTPUT_FORMATS)}"
        )
    return normalized


def _get_dm_output_format(config: Any) -> str:
    output_format = _read_nested(config, "dm_generator.output_format", "csv")
    return _normalize_dm_output_format(output_format)


def _get_config_dir(config: Any) -> Path:
    config_dir = _read_nested(config, "config_dir")
    if config_dir is not None:
        return Path(config_dir)
    return Path.cwd()


def _resolve_config_path(config: Any, path_value: Any) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return _get_config_dir(config) / path


def resolve_export_dir(config: Any) -> Path:
    export_dir = _read_nested(config, "export.dir")
    if export_dir is None:
        raise ValueError("config must specify export.dir")
    return _resolve_config_path(config, export_dir)


def resolve_dm_filepath(config: Any) -> Path:
    """Resolve the distance matrix path according to the RGT README.

    Relative paths are resolved from the configuration file directory. The only
    supported explicit distance-matrix path is root-level ``dm_filepath``. When
    it is omitted, the default is ``<export.dir>/dm.csv`` for csv output and
    ``<export.dir>/dm.h5`` for hdf output.
    """
    output_format = _get_dm_output_format(config)
    dm_filepath = _read_nested(config, "dm_filepath")
    if dm_filepath is None:
        extension = "h5" if output_format == "hdf" else "csv"
        return resolve_export_dir(config) / f"dm.{extension}"
    return _resolve_config_path(config, dm_filepath)


def resolve_dist_filepath(config: Any) -> Path:
    """Resolve the path of the distance matrix of edge lengths along the fastest paths.

    Mirrors :func:`resolve_dm_filepath`: the explicit path is root-level
    ``dist_filepath``; when it is omitted, the default is ``<export.dir>/dist.csv``
    for csv output and ``<export.dir>/dist.h5`` for hdf output.
    """
    output_format = _get_dm_output_format(config)
    dist_filepath = _read_nested(config, "dist_filepath")
    if dist_filepath is None:
        extension = "h5" if output_format == "hdf" else "csv"
        return resolve_export_dir(config) / f"dist.{extension}"
    return _resolve_config_path(config, dist_filepath)


def _is_distance_matrix_requested(config: Any) -> bool:
    return bool(_read_nested(config, "dm_generator.distance_matrix", False))


_DEFAULT_SPEED_MPS = 14
"""Speed used when edges have no speed and ``dm_generator.default_speed_kmh`` is not set (about 50 km/h)."""


def _get_default_speed_mps(config: Any) -> float:
    """Default edge speed in m/s from ``dm_generator.default_speed_kmh``."""
    speed_kmh = _read_nested(config, "dm_generator.default_speed_kmh")
    if speed_kmh is None:
        return _DEFAULT_SPEED_MPS
    speed_kmh = float(speed_kmh)
    if speed_kmh <= 0:
        raise ValueError(f"dm_generator.default_speed_kmh must be positive, got {speed_kmh}")
    return speed_kmh / 3.6


def _get_speed_factor(config: Any) -> float:
    """Multiplier of all edge speeds from ``dm_generator.speed_factor`` (default 1)."""
    speed_factor = _read_nested(config, "dm_generator.speed_factor")
    if speed_factor is None:
        return 1.0
    speed_factor = float(speed_factor)
    if speed_factor <= 0:
        raise ValueError(f"dm_generator.speed_factor must be positive, got {speed_factor}")
    return speed_factor


def generate_dm(
    config: Dict,
    nodes: Optional[gpd.GeoDataFrame],
    edges: Optional[gpd.GeoDataFrame],
    allow_zero_length_edges: bool = True
):
    output_format = _get_dm_output_format(config)
    export_dir = resolve_export_dir(config)
    map_dir = export_dir / 'map'

    # load nodes and edges if not provided
    if nodes is None:
        nodes_file_path = map_dir / 'nodes.csv'
        nodes = gpd.read_file(nodes_file_path)
        edges_file_path = map_dir / 'edges.csv'
        edges = gpd.read_file(edges_file_path)

    dm_file_path = Path(os.path.abspath(resolve_dm_filepath(config)))
    output_paths = [dm_file_path]
    distance_matrix = _is_distance_matrix_requested(config)
    if distance_matrix:
        dist_file_path = Path(os.path.abspath(resolve_dist_filepath(config)))
        output_paths.append(dist_file_path)
    if all(path.exists() for path in output_paths):
        logging.info('Skipping DM generation, the file is already generated.')
        return

    logging.info(f"Generating distance matrix ({output_format}) in {dm_file_path}")
    if distance_matrix:
        logging.info(f"Generating distance matrix of the lengths along the fastest paths in {dist_file_path}")

    # length to travel time conversion
    speed_factor = _get_speed_factor(config)
    if 'speed' in edges:
        logging.info("Using real speed from edges multiplied by %s", speed_factor)
        speeds = pd.to_numeric(edges['speed'])
        if speeds.isna().any() or (speeds <= 0).any():
            raise ValueError("Some edges have a missing or non-positive speed")
        # estimated travel time in seconds
        edges['travel_time'] = (
            pd.to_numeric(edges['length']) / (speeds * speed_factor) * 3.6
        ).round().astype(int)
    else:
        speed_mps = _get_default_speed_mps(config) * speed_factor
        logging.info('Using default speed of %.1f km/h', speed_mps * 3.6)
        try:
            edges['travel_time'] = edges['length'].apply(lambda x: round(int(x) / speed_mps))
        except ValueError as v:
            logging.warning("Suspicious max speed, trying float conversion: %s", v)
            edges['travel_time'] = edges['length'].apply(lambda x: round(float(x) / speed_mps))

    if not allow_zero_length_edges:
        edges.loc[edges['travel_time'] == 0, 'travel_time'] = 1

    # input of shortestPathsPreprocessor in its csv format: a directory with nodes.csv and edges.csv
    input_dir = map_dir / 'dm_input'
    input_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({'id': range(len(nodes))}).to_csv(input_dir / 'nodes.csv', sep='\t', index=False)
    tool_edges = pd.DataFrame({'u': edges['u'], 'v': edges['v'], 'cost': edges['travel_time']})
    if distance_matrix:
        # the tool accumulates the lengths along the fastest paths and rounds them to metres
        tool_edges['secondary_cost'] = pd.to_numeric(edges['length'])
    tool_edges.to_csv(input_dir / 'edges.csv', sep='\t', index=False)

    # the tool appends the extension of the output format to the output paths
    command = [
        "shortestPathsPreprocessor",
        "create",
        "-m",
        "dm",
        "-f",
        "csv",
        "-i",
        str(input_dir.absolute()),
        "-o",
        str(dm_file_path.with_suffix("")),
        "--preprocessing-mode",
        "slow",
        "--output-format",
        output_format,
    ]
    if distance_matrix:
        command += ["--secondary-output-path", str(dist_file_path.with_suffix(""))]

    roadgraphtool.exec.call_executable(command)
    for path in output_paths:
        tool_output_stem = path.with_suffix("")
        tool_output_path = tool_output_stem.with_name(tool_output_stem.name + _DM_TOOL_EXTENSIONS[output_format])
        if tool_output_path != path:
            tool_output_path.replace(path)
