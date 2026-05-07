import logging
from typing import List

import geopandas as gpd
import pandas as pd
from shapely import geometry

from roadgraphtool.db import db
from roadgraphtool.overpass_client import elements_by_type, query_json_from_config

_HIGHWAY_FILTER = (
    'highway~"(motorway|motorway_link|trunk|trunk_link|primary|primary_link|'
    'secondary|secondary_link|tertiary|tertiary_link|unclassified|unclassified_link|'
    'residential|residential_link|living_street)"'
)


def _polygons_from_geom(area_poly: geometry.base.BaseGeometry) -> List[geometry.Polygon]:
    if area_poly.geom_type == "Polygon":
        return [area_poly]
    if area_poly.geom_type == "MultiPolygon":
        return list(area_poly.geoms)
    if hasattr(area_poly, "geoms"):
        polys = [g for g in area_poly.geoms if g.geom_type == "Polygon"]
        if polys:
            return polys
    raise ValueError(
        f"Area geometry type {area_poly.geom_type!r} is not supported for Overpass import "
        "(expected Polygon or MultiPolygon)."
    )


def _poly_to_overpass_arg(poly: geometry.Polygon) -> str:
    """Space-separated lat lon pairs for Overpass ``(poly:\"...\")``."""
    return " ".join(f"{lat} {lon}" for lon, lat in poly.exterior.coords)


def _overpass_timeout_s(config) -> int:
    ov = getattr(config, "overpass", None)
    if ov is not None and hasattr(ov, "timeout_s"):
        try:
            return max(1, int(ov.timeout_s))
        except (TypeError, ValueError):
            pass
    return 25


def _run_overpass_backend(config, area_id: int, area_poly: geometry.base.BaseGeometry) -> int:
    """Download highway ways inside *area_poly* from Overpass and insert into DB for *area_id*."""
    logging.info("Downloading road network from Overpass API for area_id=%s", area_id)

    polys = _polygons_from_geom(area_poly)
    timeout = _overpass_timeout_s(config)
    way_lines = "\n".join(
        f'        way[{_HIGHWAY_FILTER}](poly:"{_poly_to_overpass_arg(p)}");'
        for p in polys
    )
    query = f"""
[out:json][timeout:{timeout}];
(
{way_lines}
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
        if "id" in n and "lat" in n and "lon" in n:
            node_coord[int(n["id"])] = (float(n["lon"]), float(n["lat"]))

    logging.info("Importing %s nodes", len(node_coord))
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

    nodes_ways_list = []
    ways_list = []

    logging.info("Importing %s ways", len(ways))
    for way in ways:
        way_id = int(way["id"])
        way_nodes = [int(nid) for nid in way.get("nodes", [])]
        if not way_nodes:
            continue

        for position, node_id in enumerate(way_nodes):
            nodes_ways_list.append(
                {'node_id': node_id, 'way_id': way_id, 'position': position}
            )

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


def run_overpass_import(config, area_id: int):
    """Backward-compatible: resolve polygon from DB and run Overpass import."""
    from roadgraphtool.road_import import get_area_polygon

    poly = get_area_polygon(config, area_id)
    if poly is None:
        raise ValueError(f"No geometry for area id {area_id} in schema {config.schema}.areas.")
    return _run_overpass_backend(config, area_id, poly)
