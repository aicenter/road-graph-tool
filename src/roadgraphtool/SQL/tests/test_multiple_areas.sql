-- Test suite for multiple areas in one schema: the contraction, the strong components, and the node selection of
-- an area must not depend on the other areas, even if the areas overlap.
--
-- Test network (all ways are two-way):
--
--                     110
--                      |
--   101 - 102 - 103 - 104 - 105 - 106 - 107
--
-- Area 9001 contains the whole network: 104 is an intersection, 102, 103, 105, and 106 are contracted.
-- Area 9002 is nested in area 9001 and contains only 103, 104, and 105: 103 and 105 are dead ends there, and
-- 104 is contracted.

CREATE OR REPLACE FUNCTION prepare_multiple_areas() RETURNS VOID AS $$
BEGIN
    INSERT INTO areas (id, name, geom)
    VALUES
        (9001, 'Test area with the whole network', ST_Multi(ST_MakeEnvelope(0.5, -0.5, 7.5, 1.5, 4326))),
        (9002, 'Nested test area', ST_Multi(ST_MakeEnvelope(2.5, -0.5, 5.5, 0.5, 4326))),
        (9003, 'Test area without network', ST_Multi(ST_MakeEnvelope(20, 20, 21, 21, 4326)));

    INSERT INTO nodes (id, geom, area)
    SELECT 100 + x, ST_SetSRID(ST_MakePoint(x, 0), 4326), 9001
    FROM generate_series(1, 7) AS x;
    INSERT INTO nodes (id, geom, area) VALUES (110, ST_SetSRID(ST_MakePoint(4, 1), 4326), 9001);

    INSERT INTO ways (id, geom, area, "from", "to", oneway)
    VALUES
        (101, ST_GeomFromText('LINESTRING(1 0, 2 0, 3 0, 4 0, 5 0, 6 0, 7 0)', 4326), 9001, 101, 107, false),
        (102, ST_GeomFromText('LINESTRING(4 0, 4 1)', 4326), 9001, 104, 110, false);

    INSERT INTO nodes_ways (way_id, node_id, "position", area)
    SELECT 101, 100 + x, x - 1, 9001
    FROM generate_series(1, 7) AS x;
    INSERT INTO nodes_ways (way_id, node_id, "position", area) VALUES (102, 104, 0, 9001), (102, 110, 1, 9001);
END;
$$ LANGUAGE plpgsql;

-- Edges of the area as [from, to] rows
CREATE OR REPLACE FUNCTION get_multiple_areas_edges(p_area_id integer) RETURNS bigint[] AS $$
    SELECT coalesce(
        array_agg(ARRAY[edges."from", edges."to"] ORDER BY edges."from", edges."to"), ARRAY[]::bigint[]
    )
    FROM edges
    WHERE edges.area = p_area_id;
$$ LANGUAGE sql;

-- Nodes with the strong components of the area as [node, component] rows
CREATE OR REPLACE FUNCTION get_multiple_areas_components(p_area_id integer) RETURNS bigint[] AS $$
    SELECT coalesce(
        array_agg(ARRAY[component_data.node_id, component_data.component_id] ORDER BY component_data.node_id),
        ARRAY[]::bigint[]
    )
    FROM component_data
    WHERE component_data.area = p_area_id;
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION get_multiple_areas_network_nodes(p_area_id integer) RETURNS bigint[] AS $$
    SELECT coalesce(array_agg(network_nodes.id ORDER BY network_nodes.index), ARRAY[]::bigint[])
    FROM select_network_nodes_in_area(p_area_id::smallint) AS network_nodes;
$$ LANGUAGE sql;

-- Checks the edges, strong components, and network nodes of both test areas
CREATE OR REPLACE FUNCTION validate_multiple_areas(test_name text) RETURNS SETOF TEXT AS $$
BEGIN
    RETURN NEXT is(
        get_multiple_areas_edges(9001),
        ARRAY[[101, 104], [104, 101], [104, 107], [104, 110], [107, 104], [110, 104]]::bigint[],
        test_name || ': edges of the whole network area'
    );
    RETURN NEXT is(
        get_multiple_areas_edges(9002),
        ARRAY[[103, 105], [105, 103]]::bigint[],
        test_name || ': edges of the nested area'
    );
    RETURN NEXT is(
        get_multiple_areas_components(9001),
        ARRAY[[101, 0], [104, 0], [107, 0], [110, 0]]::bigint[],
        test_name || ': strong components of the whole network area'
    );
    RETURN NEXT is(
        get_multiple_areas_components(9002),
        ARRAY[[103, 0], [105, 0]]::bigint[],
        test_name || ': strong components of the nested area'
    );
    RETURN NEXT is(
        get_multiple_areas_network_nodes(9001),
        ARRAY[101, 104, 107, 110]::bigint[],
        test_name || ': network nodes of the whole network area'
    );
    RETURN NEXT is(
        get_multiple_areas_network_nodes(9002),
        ARRAY[103, 105]::bigint[],
        test_name || ': network nodes of the nested area'
    );
END;
$$ LANGUAGE plpgsql;

-- The whole network area is processed first: the nested area must not use its contraction
CREATE OR REPLACE FUNCTION test_multiple_areas_nested_area_last() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();

    CALL contract_graph_in_area(9001::smallint, 4326);
    CALL compute_strong_components(9001::smallint);
    CALL contract_graph_in_area(9002::smallint, 4326);
    CALL compute_strong_components(9002::smallint);

    RETURN QUERY SELECT * FROM validate_multiple_areas('Nested area last');
END;
$$ LANGUAGE plpgsql;

-- The nested area is processed first: the whole network area must not use its contraction
CREATE OR REPLACE FUNCTION test_multiple_areas_nested_area_first() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();

    CALL contract_graph_in_area(9002::smallint, 4326);
    CALL compute_strong_components(9002::smallint);
    CALL contract_graph_in_area(9001::smallint, 4326);
    CALL compute_strong_components(9001::smallint);

    RETURN QUERY SELECT * FROM validate_multiple_areas('Nested area first');
END;
$$ LANGUAGE plpgsql;

-- Both areas are contracted before the strong components are computed: the components of an area must be
-- computed from the edges of that area only
CREATE OR REPLACE FUNCTION test_multiple_areas_components_after_both_contractions() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();

    CALL contract_graph_in_area(9001::smallint, 4326);
    CALL contract_graph_in_area(9002::smallint, 4326);
    CALL compute_strong_components(9001::smallint);
    CALL compute_strong_components(9002::smallint);

    RETURN QUERY SELECT * FROM validate_multiple_areas('Components after both contractions');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_multiple_areas_contraction_of_contracted_area_fails() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();
    CALL contract_graph_in_area(9001::smallint, 4326);

    RETURN NEXT throws_ok(
        'CALL contract_graph_in_area(9001::smallint, 4326)',
        'Area 9001 already has edges. To contract it again, remove them first with wipe_area_results.',
        'Contraction of an area with edges is rejected'
    );
    RETURN NEXT is(
        (SELECT count(*) FROM edges WHERE area = 9001), 6::bigint, 'The edges of the area are not duplicated'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_multiple_areas_contraction_without_road_segments_fails() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();

    RETURN NEXT throws_ok(
        'CALL contract_graph_in_area(9003::smallint, 4326)',
        'No road segments in area 9003',
        'Contraction of an area without road segments is rejected'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_multiple_areas_components_without_edges_fail() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();
    -- the edges of another area in the same place must not be used
    CALL contract_graph_in_area(9001::smallint, 4326);

    RETURN NEXT throws_ok(
        'CALL compute_strong_components(9002::smallint)',
        'Area 9002 has no edges. Contract the graph in the area first.',
        'Strong components of an area without edges are rejected'
    );
    RETURN NEXT throws_ok(
        'CALL compute_strong_components(9004::smallint)',
        'The target area with id 9004 does not exist',
        'Strong components of a missing area are rejected'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_multiple_areas_components_of_computed_area_fail() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();
    CALL contract_graph_in_area(9001::smallint, 4326);
    CALL compute_strong_components(9001::smallint);

    RETURN NEXT throws_ok(
        'CALL compute_strong_components(9001::smallint)',
        'Area 9001 already has strong components. To compute them again, remove them first with wipe_area_results.',
        'Strong components of an area with components are rejected'
    );
END;
$$ LANGUAGE plpgsql;

-- The results of one area are wiped and computed again, the other area is not touched
CREATE OR REPLACE FUNCTION test_multiple_areas_wipe_area_results() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_multiple_areas();
    CALL contract_graph_in_area(9001::smallint, 4326);
    CALL compute_strong_components(9001::smallint);
    CALL contract_graph_in_area(9002::smallint, 4326);
    CALL compute_strong_components(9002::smallint);

    CALL wipe_area_results(9001::smallint);

    RETURN NEXT is(get_multiple_areas_edges(9001), ARRAY[]::bigint[], 'Wipe: edges of the wiped area');
    RETURN NEXT is(get_multiple_areas_components(9001), ARRAY[]::bigint[], 'Wipe: components of the wiped area');
    RETURN NEXT is(
        get_multiple_areas_edges(9002), ARRAY[[103, 105], [105, 103]]::bigint[], 'Wipe: edges of the other area'
    );
    RETURN NEXT is(
        get_multiple_areas_components(9002), ARRAY[[103, 0], [105, 0]]::bigint[], 'Wipe: components of the other area'
    );
    RETURN NEXT is((SELECT count(*) FROM nodes WHERE area = 9001), 8::bigint, 'Wipe: the nodes are kept');
    RETURN NEXT is((SELECT count(*) FROM ways WHERE area = 9001), 2::bigint, 'Wipe: the ways are kept');

    CALL contract_graph_in_area(9001::smallint, 4326);
    CALL compute_strong_components(9001::smallint);

    RETURN QUERY SELECT * FROM validate_multiple_areas('Computed again after the wipe');

    RETURN NEXT throws_ok(
        'CALL wipe_area_results(9004::smallint)',
        'The target area with id 9004 does not exist',
        'Wipe of a missing area is rejected'
    );
END;
$$ LANGUAGE plpgsql;

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('multiple_areas'); -- runs all tests
-- SELECT * FROM mob_group_runtests('multiple_areas_wipe_area_results'); -- runs a single test
