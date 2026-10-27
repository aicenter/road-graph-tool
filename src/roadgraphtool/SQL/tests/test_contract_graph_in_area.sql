-- Test suite for contract_graph_in_area procedure
-- Test case 1: Simple graph with three nodes where node 2 should be contracted

-- Renamed startup function to avoid pgtap auto-execution
CREATE OR REPLACE FUNCTION prepare_contract_graph_area() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of prepare_contract_graph_area() started';
    
    -- Create test area that contains nodes at [0,0]
    INSERT INTO areas (id, name, geom)
    VALUES (
        9999,  -- high ID to avoid conflicts
        'Test Area',
        ST_Buffer(ST_SetSRID(ST_MakePoint(0, 0), 4326), 0.001)  -- small buffer around [0,0]
    );
    
END;
$$ LANGUAGE plpgsql;

-- Shared validation function
CREATE OR REPLACE FUNCTION validate_contracted_nodes(expected_contracted_nodes bigint[], test_name text) RETURNS SETOF TEXT AS $$
DECLARE
    actual_contracted_nodes bigint[];
BEGIN
    -- Get actual contracted nodes
    SELECT ARRAY(SELECT id FROM nodes WHERE contracted = TRUE)::bigint[] INTO actual_contracted_nodes;
    
    -- NULL check
    IF actual_contracted_nodes IS NULL THEN
        RETURN NEXT fail(test_name || ': Contracted nodes are NULL');
        RETURN;
    END IF;
    
    -- Compare results
    IF array_length(actual_contracted_nodes, 1) != array_length(expected_contracted_nodes, 1) THEN
        RETURN NEXT fail(test_name || ': Number of contracted nodes does not match. Expected ' ||
            array_length(expected_contracted_nodes, 1) || ', got ' || array_length(actual_contracted_nodes, 1));
    ELSE
        RETURN NEXT pass(test_name || ': Number of contracted nodes matches expected count');

        IF NOT (actual_contracted_nodes @> expected_contracted_nodes AND expected_contracted_nodes @> actual_contracted_nodes) THEN
            RETURN NEXT fail(test_name || ': Contracted nodes do not match. Expected ' ||
                             array_to_string(expected_contracted_nodes, ',') || ', got ' || array_to_string(actual_contracted_nodes, ','));
        ELSE
            RETURN NEXT pass(test_name || ': Contracted nodes match expected values');
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Test function for the first case
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_three_node_chain() RETURNS SETOF TEXT AS $$
DECLARE
    expected_contracted_nodes bigint[] := ARRAY[2]; -- node 2 should be contracted
BEGIN
    PERFORM prepare_contract_graph_area(); -- Ensure area exists
    RAISE NOTICE 'execution of test_contract_graph_in_area_three_node_chain() started';
    
    -- Setup test data
    PERFORM load_graphml_to_nodes_edges('test_1');
    
    -- Perform contraction
    CALL contract_graph_in_area(9999::smallint, 4326);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contracted_nodes(expected_contracted_nodes, 'Three node chain test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the second case (no contraction expected)
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_no_contraction() RETURNS SETOF TEXT AS $$
DECLARE
    expected_contracted_nodes bigint[] := ARRAY[]::bigint[]; -- No nodes should be contracted
BEGIN
    PERFORM prepare_contract_graph_area(); -- Ensure area exists
    RAISE NOTICE 'execution of test_contract_graph_in_area_no_contraction() started';
    
    -- Setup test data
    PERFORM load_graphml_to_nodes_edges('test_2');
    
    -- Perform contraction
    CALL contract_graph_in_area(9999::smallint, 4326);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contracted_nodes(expected_contracted_nodes, 'No contraction test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the third case (no contraction expected)
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_test_3() RETURNS SETOF TEXT AS $$
DECLARE
    expected_contracted_nodes bigint[] := ARRAY[]::bigint[]; -- No nodes should be contracted
BEGIN
    PERFORM prepare_contract_graph_area(); -- Ensure area exists
    RAISE NOTICE 'execution of test_contract_graph_in_area_test_3() started';
    
    -- Setup test data
    PERFORM load_graphml_to_nodes_edges('test_3');
    
    -- Perform contraction
    CALL contract_graph_in_area(9999::smallint, 4326);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contracted_nodes(expected_contracted_nodes, 'Test 3 graph - no contraction');
END;
$$ LANGUAGE plpgsql;

-- Test function for the fourth case (single bidirectional contraction)
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_single_bidirectional_contraction() RETURNS SETOF TEXT AS $$
DECLARE
    expected_contracted_nodes bigint[] := ARRAY[2]; -- Node 2 should be contracted
BEGIN
    PERFORM prepare_contract_graph_area(); -- Ensure area exists
    RAISE NOTICE 'execution of test_contract_graph_in_area_single_bidirectional_contraction() started';
    
    -- Setup test data
    PERFORM load_graphml_to_nodes_edges('single_bidirectional_contraction');
    
    -- Perform contraction
    CALL contract_graph_in_area(9999::smallint, 4326);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contracted_nodes(expected_contracted_nodes, 'Single bidirectional contraction test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the fifth case (single bidirectional contraction with parallel edge, no contraction)
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_single_bidirectional_and_parallel() RETURNS SETOF TEXT AS $$
DECLARE
    expected_contracted_nodes bigint[] := ARRAY[]::bigint[]; -- No nodes should be contracted
BEGIN
    PERFORM prepare_contract_graph_area(); -- Ensure area exists
    RAISE NOTICE 'execution of test_contract_graph_in_area_single_bidirectional_and_parallel() started';
    
    -- Setup test data
    PERFORM load_graphml_to_nodes_edges('single_bidirectional_contraction_and_parallel_edge');
    
    -- Perform contraction
    CALL contract_graph_in_area(9999::smallint, 4326);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contracted_nodes(expected_contracted_nodes, 'Single bidirectional and parallel edge test');
END;
$$ LANGUAGE plpgsql;

-- Sets the maxspeed tag of the test way from p_from_node to p_to_node
CREATE OR REPLACE FUNCTION set_test_way_maxspeed(p_from_node bigint, p_to_node bigint, p_maxspeed text) RETURNS VOID AS $$
BEGIN
    INSERT INTO tags ("key") VALUES ('maxspeed') ON CONFLICT ("key") DO NOTHING;
    INSERT INTO ways_tags (way_id, tag_id, tag_value)
    SELECT ways.id, tags.id, p_maxspeed
    FROM ways
        JOIN tags ON tags."key" = 'maxspeed'
    WHERE ways.area = 9999 AND ways."from" = p_from_node AND ways."to" = p_to_node;
END;
$$ LANGUAGE plpgsql;

-- Edges of the test area as [from, to, speed] rows
CREATE OR REPLACE FUNCTION get_test_edge_speeds() RETURNS bigint[] AS $$
    SELECT array_agg(ARRAY[edges."from", edges."to", edges.speed::bigint] ORDER BY edges."from", edges."to")
    FROM edges
    WHERE edges.area = 9999;
$$ LANGUAGE sql;

-- Posted speeds, the same speed along the chain 1 -> 2 -> 3: node 2 is contracted, the edge keeps the speed
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_posted_uniform_speed() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_contract_graph_area();
    PERFORM load_graphml_to_nodes_edges('test_1');
    PERFORM set_test_way_maxspeed(1, 2, '50');
    PERFORM set_test_way_maxspeed(2, 3, '50 km/h');

    CALL contract_graph_in_area(9999::smallint, 4326, 'posted', '{"default": 30}'::jsonb);

    RETURN QUERY SELECT * FROM validate_contracted_nodes(ARRAY[2]::bigint[], 'Posted uniform speed test');
    RETURN NEXT is(get_test_edge_speeds(), ARRAY[[1, 3, 50]]::bigint[], 'Posted uniform speed test: edge speed');
END;
$$ LANGUAGE plpgsql;

-- Posted speeds, the speed changes in node 2 of the chain 1 -> 2 -> 3: node 2 is kept, each edge has its speed
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_posted_speed_change() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_contract_graph_area();
    PERFORM load_graphml_to_nodes_edges('test_1');
    PERFORM set_test_way_maxspeed(1, 2, '50');
    PERFORM set_test_way_maxspeed(2, 3, '30');

    CALL contract_graph_in_area(9999::smallint, 4326, 'posted', '{"default": 40}'::jsonb);

    RETURN QUERY SELECT * FROM validate_contracted_nodes(ARRAY[]::bigint[], 'Posted speed change test');
    RETURN NEXT is(
        get_test_edge_speeds(), ARRAY[[1, 2, 50], [2, 3, 30]]::bigint[], 'Posted speed change test: edge speeds'
    );
END;
$$ LANGUAGE plpgsql;

-- Posted speeds without maxspeed tags: the default speed is used
CREATE OR REPLACE FUNCTION test_contract_graph_in_area_posted_default_speed() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_contract_graph_area();
    PERFORM load_graphml_to_nodes_edges('test_1');

    CALL contract_graph_in_area(9999::smallint, 4326, 'posted', '{"default": 40}'::jsonb);

    RETURN QUERY SELECT * FROM validate_contracted_nodes(ARRAY[2]::bigint[], 'Posted default speed test');
    RETURN NEXT is(get_test_edge_speeds(), ARRAY[[1, 3, 40]]::bigint[], 'Posted default speed test: edge speed');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_contract_graph_in_area_unknown_speed_source() RETURNS SETOF TEXT AS $$
BEGIN
    PERFORM prepare_contract_graph_area();
    PERFORM load_graphml_to_nodes_edges('test_1');

    RETURN NEXT throws_ok(
        $sql$CALL contract_graph_in_area(9999::smallint, 4326, 'measured')$sql$,
        'Unsupported speed source: measured. Supported: none, fcd, posted.',
        'Unknown speed source is rejected'
    );
END;
$$ LANGUAGE plpgsql;

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('contract_graph_in_area'); -- runs all tests
-- SELECT * FROM mob_group_runtests('contract_graph_in_area_posted'); -- runs the posted speed tests
-- SELECT * FROM mob_group_runtests('contract_graph_in_area_three_node_chain'); -- runs a single test
