import logging
import geopandas as gpd

from roadgraphtool.db import db


def get_map_nodes_from_db(area_id: int) -> gpd.GeoDataFrame:
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

    return db.execute_query_to_geopandas(sql)
