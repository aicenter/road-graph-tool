import os.path
import logging
import pandas as pd
from typing import Dict
import geopandas as gpd

import roadgraphtool.exec


def generate_dm(config: Dict, nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, allow_zero_length_edges: bool = True):
    if 'dm_filepath' in config:
        dm_file_path = config['dm_filepath']
    else:
        dm_file_path = os.path.join(config['area_dir'], 'dm')

    abs_path = os.path.abspath(dm_file_path)
    if os.path.exists(abs_path):
        logging.info('Skipping DM generation, the file is already generated.')
    else:
        logging.info(f"Generating distance matrix in {abs_path}")
        map_dir = config['map']['path']
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
