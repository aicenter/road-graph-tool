import yaml
import os.path
import logging
import pandas as pd
from typing import Dict, Optional
import geopandas as gpd
from pathlib import Path

import roadgraphtool.exec


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


def generate_dm(
    config: Dict,
    nodes: Optional[gpd.GeoDataFrame],
    edges: Optional[gpd.GeoDataFrame],
    allow_zero_length_edges: bool = True
):
    area_dir = Path(config.export.dir)
    map_dir = area_dir / 'map'

    # load nodes and edges if not provided
    if nodes is None:
        nodes_file_path = map_dir / 'nodes.csv'
        nodes = gpd.read_file(nodes_file_path)
        edges_file_path = map_dir / 'edges.csv'
        edges = gpd.read_file(edges_file_path)

    if hasattr(config, 'dm_filepath'):
        dm_file_path = config.dm_filepath
    else:
        dm_file_path = os.path.join(area_dir, 'dm')

    abs_path = os.path.abspath(dm_file_path)
    abs_path_with_extension = abs_path + '.csv'
    if os.path.exists(abs_path) or os.path.exists(abs_path_with_extension):
        logging.info('Skipping DM generation, the file is already generated.')
    else:
        logging.info(f"Generating distance matrix in {abs_path}")
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
            "csv"
        ]

        roadgraphtool.exec.call_executable(command)
