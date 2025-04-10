import logging
from os import path, makedirs
from pathlib import Path
from typing import Dict, Tuple

import geopandas as gpd
import pandas as pd
from roadgraphtool.db import db


def get_map_nodes_from_db(area_id: int, schema='public') -> gpd.GeoDataFrame:
    logging.info("Fetching nodes from db")
    sql = f"""
    DROP TABLE IF EXISTS demand_nodes;

    CREATE TEMP TABLE demand_nodes(
        id int,
        db_id bigint,
        x float,
        y float,
        geom geometry
    );

    INSERT INTO demand_nodes
    SELECT * FROM select_network_nodes_in_area({area_id}::smallint);

    SELECT
        id,
        db_id,
        x,
        y,
        geom
    FROM demand_nodes
    """
    logging.info("Starting sql_alchemy connection")

    return db.execute_query_to_geopandas(sql, schema=schema)


def get_map_edges_from_db(config: dict, schema='public') -> gpd.GeoDataFrame:
    logging.info("Fetching edges from db")
    sql = f"""
        DROP TABLE IF EXISTS demand_nodes;
        CREATE TEMP TABLE demand_nodes(
            id int,
            db_id bigint,
            x float,
            y float,
            geom geometry
        );

        INSERT INTO demand_nodes
        SELECT * FROM select_network_nodes_in_area({config.area_id}::smallint);
    
        SELECT
            from_nodes.id AS u,
            to_nodes.id AS v,
            "from" AS db_id_from,
            "to" AS db_id_to,
            edges.geom as geom,
            st_length(st_transform(edges.geom, {config.srid})) as length,
            speed
        FROM edges
            JOIN demand_nodes from_nodes ON edges."from" = from_nodes.db_id
            JOIN demand_nodes to_nodes ON edges."to" = to_nodes.db_id
        WHERE
            edges.area = {config.area_id}::smallint -- This is to support overlapping areas. For using another 
                                                        --area for edges (like for Manhattan), new edge_are_id param 
                                                        -- should be added to config.yaml
    """
    edges = db.execute_query_to_geopandas(sql, schema=schema)

    if len(edges) == 0:
        logging.error("No edges selected")
        logging.info(sql)
        raise Exception("No edges selected")

    return edges




def add_node_highway_tags(nodes, G):
    for u, v, d in G.edges(data=True):
        if 'highway' in d.keys():
            tag = d['highway']
            tag = tag[0] if isinstance(tag, list) else tag
            nodes.loc[nodes.index[[u]], 'highway'] = tag
            nodes.loc[nodes.index[[v]], 'highway'] = tag


def _get_map_from_db(config: dict) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    nodes = get_map_nodes_from_db(config.area_id)
    logging.info(f"{len(nodes)} nodes fetched from db")
    edges = get_map_edges_from_db(config)
    logging.info(f"{len(edges)} edges fetched from db")
    return nodes, edges


def _save_map_csv(map_dir: Path, nodes: gpd.GeoDataFrame, edges: pd.DataFrame):
    map_dir.makedirs(exist_ok=True)
    nodes_path = map_dir / 'nodes.csv'
    logging.info("Saving map nodes to %s", nodes_path)
    nodes_for_export = nodes.loc[:, nodes.columns != 'geom']
    nodes_for_export.to_csv(nodes_path, sep='\t', index=False)

    edges_path = map_dir / 'edges.csv'
    logging.info("Saving map edges to %s", edges_path)
    edges_for_export = edges.loc[:, edges.columns != 'geom']
    edges_for_export.to_csv(edges_path, sep='\t', index=False)


def _save_graph_shapefile(nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, shapefile_folder_path: Path):
    logging.info("Saving map shapefile to: %s", shapefile_folder_path.absolute())

    # if save folder does not already exist, create it (shapefiles get saved as set of files)
    shapefile_folder_path.mkdir(parents=True, exist_ok=True)
    filepath_nodes = shapefile_folder_path / "nodes.shp"
    filepath_edges = shapefile_folder_path / "edges.shp"

    # save the nodes and edges as separate ESRI shapefiles
    nodes.to_file(str(filepath_nodes), driver="ESRI Shapefile", index=False, encoding="utf-8")
    edges.to_file(str(filepath_edges), driver="ESRI Shapefile", index=False, encoding="utf-8")


def export(config: Dict):
    """
    Loads filtered map nodes geodataframe. If th dataframe is not generated yet, then the map is downloaded
    and processed to obtain the filtered nodes dataframe
    :param config: instance configuration
    :return: geodataframe containing filtered nodes that are intended for demand generation
    """
    export_dir = config.export
    area_dir = Path(export_dir.dir)
    map_dir = area_dir / 'map'
    nodes_file_path = map_dir / 'nodes.csv'

    # map already generated -> load
    if path.exists(nodes_file_path):
        logging.warning("Nodes already exists %s", nodes_file_path.absolute())
        logging.warning("Exiting")

    # download and process map
    else:
        nodes, edges = _get_map_from_db(config)

        # save map to shapefile (for visualising)
        shapefile_folder_path = map_dir / "shapefiles"
        _save_graph_shapefile(nodes, edges, shapefile_folder_path)

        # save data
        makedirs(area_dir, exist_ok=True)
        _save_map_csv(map_dir, nodes, edges)

