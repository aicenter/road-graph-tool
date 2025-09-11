CREATE OR REPLACE FUNCTION _create_temp_tables()
    RETURNS VOID
    LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Creating temporary tables';

    -- Remove temporary tables if they already exist.
    DROP TABLE IF EXISTS road_segments;
    DROP TABLE IF EXISTS contractions;

    -- Create a temporary table for contractions.
    CREATE TEMP TABLE contractions (
        id integer PRIMARY KEY,
        source integer,
        target integer,
        contracted_vertex integer
    ) ON COMMIT DROP;

    -- Create a temporary table for road segments.
    CREATE TEMP TABLE road_segments (
        from_id integer,
        to_id integer,
        from_node integer,
        to_node integer,
        from_position geometry(Point, 4326),
        to_position geometry(Point, 4326),
        way_id integer,
        geom geometry(LineString, 4326),
        speed numeric,
        quality integer
    ) ON COMMIT DROP;
END;
$$;

CREATE OR REPLACE PROCEDURE create_edge_segments_from_contractions_fixture_basic_data() AS
$$
BEGIN
    RAISE NOTICE 'Creating test input data';

    -- Insert a single contraction.
    INSERT INTO contractions (id, source, target, contracted_vertex)
    VALUES (100, 1, 2, 100);

    -- Insert two road segments associated with the contraction.
    -- Road segment 1: from node 1 to the contraction (100)
    -- Road segment 2: from the contraction (100) to node 2
    INSERT INTO road_segments (from_id, to_id, from_node, to_node, from_position, to_position, way_id, geom, speed, quality)
    VALUES
        (1, 100, 1, 100, 
         ST_SetSRID(ST_Point(1, 1), 4326),
         ST_SetSRID(ST_Point(0, 0), 4326),
         1,
         ST_SetSRID(ST_MakeLine(ST_Point(1, 1), ST_Point(0, 0)), 4326),
         50, 1),
        (100, 2, 100, 2,
         ST_SetSRID(ST_Point(0, 0), 4326),
         ST_SetSRID(ST_Point(-1, -1), 4326),
         2,
         ST_SetSRID(ST_MakeLine(ST_Point(0, 0), ST_Point(-1, -1)), 4326),
         50, 1);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_create_edge_segments_from_contractions_basic() RETURNS SETOF TEXT AS
$$
BEGIN
    -- Setup the test data.
    PERFORM _create_temp_tables();
    CALL create_edge_segments_from_contractions_fixture_basic_data();

    RAISE NOTICE '--- test_create_edge_segments_from_contractions_basic ---';
    CALL create_edge_segments_from_contractions(FALSE);

    -- 1. Verify that two edge segments were created.
    RETURN NEXT is((SELECT count(*) FROM contraction_segments), 2::bigint, 'Two edge segments were created.');

    -- 2. Verify the details of the first edge segment.
    RETURN NEXT is(
        (SELECT ST_AsText(geom) FROM contraction_segments WHERE id = 100 AND from_node = 1),
        'LINESTRING(1 1,0 0)',
        'Edge segment 1 geometry is correct.'
    );
    RETURN NEXT is(
        (SELECT from_node FROM contraction_segments WHERE id = 100 AND from_node = 1),
        1,
        'Edge segment 1 from_node is correct.'
    );
    RETURN NEXT is(
        (SELECT to_node FROM contraction_segments WHERE id = 100 AND from_node = 1),
        100,
        'Edge segment 1 to_node is correct.'
    );

    -- 3. Verify the details of the second edge segment.
    RETURN NEXT is(
        (SELECT ST_AsText(geom) FROM contraction_segments WHERE id = 100 AND from_node = 100),
        'LINESTRING(0 0,-1 -1)',
        'Edge segment 2 geometry is correct.'
    );
    RETURN NEXT is(
        (SELECT from_node FROM contraction_segments WHERE id = 100 AND from_node = 100),
        100,
        'Edge segment 2 from_node is correct.'
    );
    RETURN NEXT is(
        (SELECT to_node FROM contraction_segments WHERE id = 100 AND from_node = 100),
        2,
        'Edge segment 2 to_node is correct.'
    );

END;
$$ LANGUAGE plpgsql;