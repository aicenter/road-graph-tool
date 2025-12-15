
import overpy
import pandas as pd
import geopandas as gpd
import logging

from shapely import geometry

from roadgraphtool.db import db
import roadgraphtool.insert_area


def run_overpass_import(config):
    area = config.area.name

    area_id = roadgraphtool.insert_area.genereate_area(config, f'{area} - overpass_import')

    logging.info(f"Downloading area {area} from Overpass API")

    filter = """
    highway~"(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|unclassified_link|residential|residential_link|living_street)"
    """
    query = f"""
    area[name="{area}"];
    (
        (way(area)[{filter}];)->.edges;.edges>->.nodes;
    );
    out;
    """
    api = overpy.Overpass()
    result = api.query(query)

    # nodes
    logging.info(f"Importing {len(result.nodes)} nodes")
    node_list = [{'id': node.id, 'lat': node.lat, 'lon': node.lon} for node in result.nodes]
    node_df = pd.DataFrame(node_list)
    node_gdf = gpd.GeoDataFrame(node_df, geometry=gpd.points_from_xy(node_df.lon, node_df.lat), crs="EPSG:4326")
    node_gdf.drop(columns=['lon', 'lat'], inplace=True)
    node_gdf.rename(columns={'geometry': 'geom'}, inplace=True)
    node_gdf.set_geometry('geom', inplace=True)
    node_gdf.set_index('id', inplace=True)
    db.geodataframe_to_db_table(node_gdf, "nodes", srid=4326)

    # ways and nodes_ways
    nodes_ways_list = []
    ways_list = []

    logging.info(f"Importing {len(result.ways)} ways")
    for way in result.ways:

        # add nodes to nodeways list
        for position, node_id in enumerate(way.nodes):
            nodes_ways_list.append(
                {'node_id': node_id.id, 'way_id': way.id, 'position': position}
            )

        # add the way
        ways_list.append(
            {
                'id': way.id,
                'geom': geometry.LineString([node.lon, node.lat] for node in way.nodes),
                'area': area_id,
                'from': way.nodes[0].id,
                'to': way.nodes[-1].id,
                'oneway': False}
        )

    ways_gdf = gpd.GeoDataFrame(ways_list, geometry='geom', crs="EPSG:4326")
    ways_gdf.set_index('id', inplace=True)
    db.geodataframe_to_db_table(ways_gdf, "ways")

    nodes_ways_df = pd.DataFrame(nodes_ways_list)
    db.dataframe_to_db_table(nodes_ways_df, "nodes_ways", stored_index=False)

    return area_id
