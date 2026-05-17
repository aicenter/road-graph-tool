import yaml
import os.path
import logging
import pandas as pd
from typing import Any, Dict, List, Optional, Union
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


def _get_area_dir(config: Any) -> Path:
    export_dir = _read_nested(config, "export.dir")
    if export_dir is not None:
        return Path(export_dir)
    area_dir = _read_nested(config, "area_dir")
    if area_dir is not None:
        return Path(area_dir)
    raise ValueError("config must specify export.dir or area_dir")


def _get_dm_filepath(config: Any, area_dir: Path, output_format: str) -> Path:
    dm_filepath = _read_nested(config, "dm_filepath")
    if dm_filepath is None:
        dm_filepath = _read_nested(config, "dm_generator.dm_filepath")
    if dm_filepath is None:
        dm_filepath = area_dir / "dm"
    return Path(dm_filepath)


def _dm_output_candidate_paths(dm_filepath: Union[str, Path], output_format: str) -> List[Path]:
    base = Path(dm_filepath)
    if output_format == "hdf":
        if base.suffix.lower() in {".h5", ".hdf5"}:
            return [base]
        return [base, base.with_suffix(".h5"), Path(str(base) + ".h5")]
    if base.suffix.lower() == ".csv":
        return [base]
    return [base, Path(str(base) + ".csv")]


def _dm_output_exists(dm_filepath: Union[str, Path], output_format: str) -> bool:
    return any(path.exists() for path in _dm_output_candidate_paths(dm_filepath, output_format))


def generate_dm(
    config: Dict,
    nodes: Optional[gpd.GeoDataFrame],
    edges: Optional[gpd.GeoDataFrame],
    allow_zero_length_edges: bool = True
):
    output_format = _get_dm_output_format(config)
    area_dir = _get_area_dir(config)
    map_dir = area_dir / 'map'

    # load nodes and edges if not provided
    if nodes is None:
        nodes_file_path = map_dir / 'nodes.csv'
        nodes = gpd.read_file(nodes_file_path)
        edges_file_path = map_dir / 'edges.csv'
        edges = gpd.read_file(edges_file_path)

    dm_file_path = _get_dm_filepath(config, area_dir, output_format)
    abs_path = os.path.abspath(dm_file_path)
    if _dm_output_exists(abs_path, output_format):
        logging.info('Skipping DM generation, the file is already generated.')
    else:
        logging.info(f"Generating distance matrix ({output_format}) in {abs_path}")
        map_dir.mkdir(parents=True, exist_ok=True)
        xeng_file_path = os.path.join(map_dir, 'map.xeng')
        xeng_file_path = os.path.abspath(xeng_file_path)

        # length to travel time conversion, 50 km/h
        if 'speed' in edges:
            logging.info("Using real speed from edges")
            # estimated travel time in seconds
            edges['travel_time'] = (edges['length'] / edges['speed'] * 3.6).round().astype(int)
        else:
            logging.info('Using default speed of 50 km/h')
            try:
                edges['travel_time'] = edges['length'].apply(lambda x: round(int(x) / 14))
            except ValueError as v:
                logging.warning("Suspicious max speed, trying float conversion: %s", v)
                edges['travel_time'] = edges['length'].apply(lambda x: round(float(x) / 14))

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
