
import pandas as pd
import geopandas as gpd
import logging

from shapely import geometry

from roadgraphtool.db import db
from roadgraphtool.overpass_client import elements_by_type, query_json_from_config


def run_overpass_import(config, area_id: int):
    area = config.area.name

    logging.info(f"Downloading area {area} from Overpass API")

    filter = """
    highway~"(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|unclassified_link|residential|residential_link|living_street)"
    """
    query = f"""
    [out:json][timeout:25];
    area[name="{area}"];
    (
        way(area)[{filter}];
    );
    (._;>;);
    out body;
    """
    overpass_json = query_json_from_config(config, query, build=False)
    by_type = elements_by_type(overpass_json)

    nodes = by_type["node"]
    ways = by_type["way"]

    node_coord = {}
    for n in nodes:
        # Overpass JSON nodes provide lat/lon directly
        if "id" in n and "lat" in n and "lon" in n:
            node_coord[int(n["id"])] = (float(n["lon"]), float(n["lat"]))

    # nodes
    logging.info(f"Importing {len(node_coord)} nodes")
    node_list = [
        {"id": node_id, "lat": lat, "lon": lon}
        for node_id, (lon, lat) in node_coord.items()
    ]
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

    logging.info(f"Importing {len(ways)} ways")
    for way in ways:
        way_id = int(way["id"])
        way_nodes = [int(nid) for nid in way.get("nodes", [])]
        if not way_nodes:
            continue

        # add nodes to nodeways list
        for position, node_id in enumerate(way_nodes):
            nodes_ways_list.append(
                {'node_id': node_id, 'way_id': way_id, 'position': position}
            )

        # add the way
        coords = [node_coord.get(nid) for nid in way_nodes]
        coords = [c for c in coords if c is not None]
        if len(coords) < 2:
            continue
        ways_list.append(
            {
                'id': way_id,
                'geom': geometry.LineString(coords),
                'area': area_id,
                'from': way_nodes[0],
                'to': way_nodes[-1],
                'oneway': False}
        )

    ways_gdf = gpd.GeoDataFrame(ways_list, geometry='geom', crs="EPSG:4326")
    ways_gdf.set_index('id', inplace=True)
    db.geodataframe_to_db_table(ways_gdf, "ways")

    nodes_ways_df = pd.DataFrame(nodes_ways_list)
    db.dataframe_to_db_table(nodes_ways_df, "nodes_ways", stored_index=False)

    return area_id
