
import osmnx as ox
import pandas as pd
import networkx as nx
import geopandas as gpd

from typing import Dict

from roadgraphtool.db import db


def run_overpass_import(config):
    graph = ox.graph_from_place(config.overpass_importer.area_name, network_type='drive')

    # upload nodes to database
    nodes_df = pd.DataFrame.from_dict(dict(graph.nodes(data=True)), orient='index')
    nodes_gdf = gpd.GeoDataFrame(nodes_df, geometry=gpd.points_from_xy(nodes_df.x, nodes_df.y), crs="EPSG:4326")
    nodes_gdf.drop(columns=['x', 'y', 'street_count'], inplace=True)
    nodes_gdf.rename(columns={'geometry': 'geom'}, inplace=True)
    nodes_gdf.set_geometry('geom', inplace=True)
    nodes_gdf.index.rename('id', inplace=True)
    db.geodataframe_to_db_table(nodes_gdf, "nodes", srid=4326)


    # upload edges to database
    edges_df = pd.DataFrame.from_dict(graph.edges(data=True))
    node_ways_list = []
    for from_node_id, to_node_id, way_id in zip(edges_df['source'], edges_df['target'], edges_df['way_id']):
        node_ways_list.append({
            'node_id': from_node_id,
            'way_id': way_id,
            'position': 0
        })
        node_ways_list.append({
            'node_id': to_node_id,
            'way_id': way_id,
            'position': 1
        })
    node_ways_df = pd.DataFrame(node_ways_list)
    db.dataframe_to_db_table(node_ways_df, 'nodes_ways')
    ways_df = edges_df.groupby('way_id').agg({'length': 'sum'}).reset_index()
    db.dataframe_to_db_table(ways_df, 'ways')
   
