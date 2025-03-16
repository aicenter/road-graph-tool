CREATE OR REPLACE PROCEDURE startup_create_edge_segments_from_contractions()
    LANGUAGE plpgsql
AS $$
BEGIN
    -- Remove temporary tables if they already exist.
    DROP TABLE IF EXISTS road_segments;
    DROP TABLE IF EXISTS contractions;

    -- Create a temporary table for contractions.
    CREATE TEMP TABLE contractions (
                                       contraction_id integer PRIMARY KEY,
                                       geom geometry(Point, 4326)
    ) ON COMMIT DROP;

    -- Create a temporary table for road segments.
    CREATE TEMP TABLE road_segments (
                                        road_id integer PRIMARY KEY,
                                        source integer,
                                        target integer,
                                        geom geometry(LineString, 4326)
    ) ON COMMIT DROP;
END;
$$;

CREATE OR REPLACE PROCEDURE create_edge_segments_from_contractions_fixture_basic_data() AS
$$
BEGIN

    -- Insert a single contraction.
    INSERT INTO contractions (contraction_id, geom)
    VALUES (100, ST_SetSRID(ST_Point(0, 0), 4326));

    -- Insert two road segments associated with the contraction.
    -- Road segment 1: from node 1 to the contraction (100)
    -- Road segment 2: from the contraction (100) to node 2
    INSERT INTO road_segments (road_id, source, target, geom)
    VALUES
        (1, 1, 100, ST_SetSRID(ST_MakeLine(ST_Point(1, 1), ST_Point(0, 0)), 4326)),
        (2, 100, 2, ST_SetSRID(ST_MakeLine(ST_Point(0, 0), ST_Point(-1, -1)), 4326));
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION test_create_edge_segments_from_contractions_basic() RETURNS SETOF TEXT AS
$$
BEGIN
    -- Setup the test data.
    CALL create_edge_segments_from_contractions_fixture_basic_data();

    RAISE NOTICE '--- test_create_edge_segments_from_contractions_basic ---';
    CALL create_edge_segments_from_contractions(FALSE);

    -- 1. Verify that two edge segments were created.
    RETURN NEXT is((SELECT count(*) FROM edge_segments), 2, 'Two edge segments were created.');

    -- 2. Verify the details of the first edge segment.
    RETURN NEXT is_deeply(
       (SELECT row(road_id, source, target, ST_AsText(geom)) FROM edge_segments WHERE road_id = 1),
       row(1, 1, 100, 'LINESTRING(1 1,0 0)'),
       'Edge segment for road 1 is correct.'
   );

-- 3. Verify the details of the second edge segment.
    RETURN NEXT is_deeply(
       (SELECT row(road_id, source, target, ST_AsText(geom)) FROM edge_segments WHERE road_id = 2),
       row(2, 100, 2, 'LINESTRING(0 0,-1 -1)'),
       'Edge segment for road 2 is correct.'
   );

    DISCARD TEMP;

END;
$$ LANGUAGE plpgsql;