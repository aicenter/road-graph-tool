import logging
import os.path
from pathlib import Path

import osmnx as ox
import pandas as pd
import networkx as nx
import geopandas as gpd
from os import path, makedirs
from typing import Dict, Tuple

from roadgraphtool.db import db
from roadgraphtool.export import get_map_nodes_from_db, get_map_edges_from_db


def add_node_highway_tags(nodes, G):
    for u, v, d in G.edges(data=True):
        if 'highway' in d.keys():
            tag = d['highway']
            tag = tag[0] if isinstance(tag, list) else tag
            nodes.loc[nodes.index[[u]], 'highway'] = tag
            nodes.loc[nodes.index[[v]], 'highway'] = tag


def _get_map_from_db(config: dict) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    nodes = get_map_nodes_from_db(config['area_id'])
    logging.info(f"{len(nodes)} nodes fetched from db")
    edges = get_map_edges_from_db(config)
    logging.info(f"{len(edges)} edges fetched from db")
    return nodes, edges


def _get_map(config) -> tuple:
    """
    Download map using map/place property from config
    :param config: config
    :return: nodes and edges
    """

    # download map using osmnx
    place = config["map"]['place']
    logging.info("Downloading map for %s", place)
    road_network = ox.graph_from_place(place, network_type='drive', simplify=True)

    # strongly connected component
    strongly_connected_components = sorted(nx.strongly_connected_components(road_network), key=len, reverse=True)
    road_network = road_network.subgraph(strongly_connected_components[0])

    logging.info("Relabeling nodes")
    road_network = nx.relabel.convert_node_labels_to_integers(road_network, label_attribute="osmid")
    nodes, edges = ox.graph_to_gdfs(road_network)

    logging.info("Processing nodes")
    if "highway" not in nodes:
        nodes["highway"] = "empty"
    nodes = nodes[['x', 'y', 'osmid', 'geometry', 'highway']]
    nodes["id"] = nodes.index
    add_node_highway_tags(nodes, road_network)

    logging.info("Processing edges")
    edges = edges.reset_index()
    edges = edges[['u', 'v', 'length', 'highway']]

    return nodes, edges


def _save_map_csv(map_dir: os.path, nodes: gpd.GeoDataFrame, edges: pd.DataFrame):
    makedirs(map_dir, exist_ok=True)
    nodes_path = path.join(map_dir, 'nodes.csv')
    logging.info("Saving map nodes to %s", nodes_path)
    nodes_for_export = nodes.loc[:, nodes.columns != 'geom']
    nodes_for_export.to_csv(nodes_path, sep='\t', index=False)

    edges_path = path.join(map_dir, 'edges.csv')
    logging.info("Saving map edges to %s", edges_path)
    edges_for_export = edges.loc[:, edges.columns != 'geom']
    edges_for_export.to_csv(edges_path, sep='\t', index=False)


def _save_graph_shapefile(nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, shapefile_folder_path: str):
    filepath = Path(shapefile_folder_path)
    logging.info("Saving map shapefile to: %s", filepath.absolute())

    # if save folder does not already exist, create it (shapefiles get saved as set of files)
    filepath.mkdir(parents=True, exist_ok=True)
    filepath_nodes = filepath / "nodes.shp"
    filepath_edges = filepath / "edges.shp"

    # save the nodes and edges as separate ESRI shapefiles
    nodes.to_file(str(filepath_nodes), driver="ESRI Shapefile", index=False, encoding="utf-8")
    edges.to_file(str(filepath_edges), driver="ESRI Shapefile", index=False, encoding="utf-8")


def get_map(config: Dict) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Loads filtered map nodes geodataframe. If th dataframe is not generated yet, then the map is downloaded
    and processed to obtain the filtered nodes dataframe
    :param config: instance configuration
    :return: geodataframe containing filtered nodes that are intended for demand generation
    """
    area_dir = config['area_dir']
    map_dir = os.path.join(area_dir, 'map')

    nodes_file_path = path.join(map_dir, 'nodes.csv')

    # map already generated -> load
    if path.exists(nodes_file_path):
        logging.info("Loading nodes from %s", path.abspath(nodes_file_path))
        nodes = pd.read_csv(nodes_file_path, index_col=None, delim_whitespace=True)
        nodes = gpd.GeoDataFrame(
            nodes,
            geometry=gpd.points_from_xy(nodes.x, nodes.y),
            crs=f'epsg:{config["map"]["SRID"]}'
        )
        edges_file_path = path.join(map_dir, 'edges.csv')
        logging.info("Loading edges from %s", path.abspath(edges_file_path))
        edges = pd.read_csv(edges_file_path, index_col=None, delim_whitespace=True)

    # download and process map
    else:
        if 'place' in config['map']:
            nodes, edges = _get_map(config)
        else:
            nodes, edges = _get_map_from_db(config)

        # save map to shapefile (for visualising)
        map_dir = config["map"]["path"]
        shapefile_folder_path = path.join(map_dir, "shapefiles")
        _save_graph_shapefile(nodes, edges, shapefile_folder_path)

        # save data
        makedirs(area_dir, exist_ok=True)
        _save_map_csv(map_dir, nodes, edges)

    # Filter nodes by config/area. Only these nodes should be used for demand/vehicle generation/selection
    if 'area' in config:
        sql = f"""SELECT geom FROM areas WHERE name = '{config['area']}'"""
        area_shape = db.execute_query_to_geopandas(sql)
        mask = nodes.within(area_shape.loc[0, 'geom'])
        nodes = nodes.loc[mask]

    # set index to id column: this is needed for the shapefile export
    nodes.set_index('id', inplace=True)

    return nodes, edges
