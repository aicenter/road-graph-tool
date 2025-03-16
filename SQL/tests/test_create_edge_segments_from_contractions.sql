CREATE OR REPLACE PROCEDURE setup_temp_tables()
    LANGUAGE plpgsql
AS $$
BEGIN
    -- Drop existing temporary tables if they exist.
    DROP TABLE IF EXISTS edge_segments;
    DROP TABLE IF EXISTS road_segments;
    DROP TABLE IF EXISTS contracted_nodes;

    -- Create temporary table for contracted nodes.
    CREATE TEMP TABLE contracted_nodes (
                                           node_id integer PRIMARY KEY,
                                           geom geometry(Point, 4326)
    ) ON COMMIT DROP;

    -- Create temporary table for road segments.
    CREATE TEMP TABLE road_segments (
                                        road_id integer PRIMARY KEY,
                                        source integer,
                                        target integer,
                                        geom geometry(LineString, 4326)
    ) ON COMMIT DROP;

    -- Create temporary table for edge segments.
    CREATE TEMP TABLE edge_segments (
                                        edge_id serial PRIMARY KEY,
                                        road_id integer,
                                        source integer,
                                        target integer,
                                        geom geometry(LineString, 4326)
    ) ON COMMIT DROP;
END;
$$;

CREATE OR REPLACE FUNCTION fixture_basic_data()
    RETURNS void AS
$$
BEGIN
    -- Set up the temporary tables.
    CALL setup_temp_tables();

    -- Insert a single contracted node.
    INSERT INTO contracted_nodes (node_id, geom)
    VALUES (100, ST_SetSRID(ST_Point(0, 0), 4326));

    -- Insert two road segments connected to the contracted node.
    -- Road segment 1: from node 1 to the contracted node (100)
    -- Road segment 2: from the contracted node (100) to node 2
    INSERT INTO road_segments (road_id, source, target, geom)
    VALUES
        (1, 1, 100, ST_SetSRID(ST_MakeLine(ST_Point(1, 1), ST_Point(0, 0)), 4326)),
        (2, 100, 2, ST_SetSRID(ST_MakeLine(ST_Point(0, 0), ST_Point(-1, -1)), 4326));
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_create_edge_segments_from_contractions_basic() RETURNS SETOF TEXT AS
$$
BEGIN
    RAISE NOTICE '--- test_create_edge_segments_from_contractions_basic ---';
    CALL create_edge_segments_from_contractions(FALSE);

END;
$$ LANGUAGE plpgsql;