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

    dm_file_path = resolve_dm_filepath(config)
    abs_path = os.path.abspath(dm_file_path)
    if Path(abs_path).exists():
        logging.info('Skipping DM generation, the file is already generated.')
    else:
        logging.info(f"Generating distance matrix ({output_format}) in {abs_path}")
        map_dir.mkdir(parents=True, exist_ok=True)
        xeng_file_path = os.path.join(map_dir, 'map.xeng')
        xeng_file_path = os.path.abspath(xeng_file_path)

        # length to travel time conversion
        if 'speed' in edges:
            logging.info("Using real speed from edges")
            # estimated travel time in seconds
            edges['travel_time'] = (edges['length'] / edges['speed'] * 3.6).round().astype(int)
        else:
            speed_mps = _get_default_speed_mps(config)
            logging.info('Using default speed of %.1f km/h', speed_mps * 3.6)
            try:
                edges['travel_time'] = edges['length'].apply(lambda x: round(int(x) / speed_mps))
            except ValueError as v:
                logging.warning("Suspicious max speed, trying float conversion: %s", v)
                edges['travel_time'] = edges['length'].apply(lambda x: round(float(x) / speed_mps))

        if not allow_zero_length_edges:
            edges.loc[edges['travel_time'] == 0, 'travel_time'] = 1

        xeng = pd.DataFrame(edges[['u', 'v', 'travel_time']])
        xeng['one_way'] = 1
        xeng.to_csv(xeng_file_path, sep=" ", header=["XGI", str(len(nodes)), str(len(edges)), ""], index=False)

        # call distance utils to generate dm
        command = [
            "shortestPathsPreprocessor",
            "create",
            "-m",
            "dm",
            "-f",
            "xengraph",
            "-i",
            xeng_file_path,
            "-o",
            abs_path,
            "--preprocessing-mode",
            "slow",
            "--output-format",
            output_format,
        ]

        roadgraphtool.exec.call_executable(command)
