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


def get_map_edges_from_db(config: dict) -> gpd.GeoDataFrame:
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
        SELECT * FROM select_network_nodes_in_area({config['area_id']}::smallint);
    
        SELECT
            from_nodes.id AS u,
            to_nodes.id AS v,
            "from" AS db_id_from,
            "to" AS db_id_to,
            edges.geom as geom,
            st_length(st_transform(edges.geom, {config['map']['SRID_plane']})) as length,
            speed
        FROM edges
            JOIN demand_nodes from_nodes ON edges."from" = from_nodes.db_id
            JOIN demand_nodes to_nodes ON edges."to" = to_nodes.db_id
        WHERE
            edges.area = {config['area_id']}::smallint -- This is to support overlapping areas. For using anohther 
                                                        --area for edges (like for Manhattan), new edge_are_id param 
                                                        -- should be added to congig.yaml
    """
    edges = db.execute_query_to_geopandas(sql)

    if len(edges) == 0:
        logging.error("No edges selected")
        logging.info(sql)
        raise Exception("No edges selected")

    return edges
