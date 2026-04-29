-- Test suite for get_restricted_nodes function
-- Test case 1: Simple graph with three nodes where n0 and n2 should be restricted
-- Test case 2: Graph with nodes 1 and 2 as restricted nodes
-- Test case 3: Graph with nodes 1, 2, and 3 as restricted nodes

-- Renamed startup function to avoid pgtap auto-execution
CREATE OR REPLACE FUNCTION prepare_restricted_nodes_test_env() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of prepare_restricted_nodes_test_env() started';
    
    -- Create temporary tables if they don't exist
    CREATE TEMPORARY TABLE IF NOT EXISTS road_segments (
        from_node bigint NOT NULL,
        to_node bigint NOT NULL
    );
    
END;
$$ LANGUAGE plpgsql;

-- Shared validation function
CREATE OR REPLACE FUNCTION validate_restricted_nodes(restricted_nodes bigint[], expected_nodes bigint[], test_name text) RETURNS SETOF TEXT AS $$
BEGIN
    -- NULL check
    IF restricted_nodes IS NULL THEN
        RETURN NEXT fail(test_name || ': Restricted nodes are NULL');
        RETURN;
    END IF;
    
    -- Compare results
    IF array_length(restricted_nodes, 1) != array_length(expected_nodes, 1) THEN
        RETURN NEXT fail(test_name || ': Number of restricted nodes does not match. Expected ' ||
            array_length(expected_nodes, 1) || ', got ' || array_length(restricted_nodes, 1));
    ELSE
        RETURN NEXT pass(test_name || ': Number of restricted nodes matches expected count');

        IF NOT (restricted_nodes @> expected_nodes AND expected_nodes @> restricted_nodes) THEN
            RETURN NEXT fail(test_name || ': Restricted nodes do not match. Expected ' ||
                             array_to_string(expected_nodes, ',') || ', got ' || array_to_string(restricted_nodes, ','));
        ELSE
            RETURN NEXT pass(test_name || ': Restricted nodes match expected values');
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Test function for the first case
CREATE OR REPLACE FUNCTION test_get_restricted_nodes_three_node_chain() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[1, 3]; -- n0 and n2 should be restricted
BEGIN
    PERFORM prepare_restricted_nodes_test_env(); -- Ensure table exists
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_node_chain() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_1');
    
    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Three node chain test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the second case
CREATE OR REPLACE FUNCTION test_get_restricted_nodes_two_restricted_nodes() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[1, 2]; -- nodes 1 and 2 should be restricted
BEGIN
    PERFORM prepare_restricted_nodes_test_env(); -- Ensure table exists
    RAISE NOTICE 'execution of test_get_restricted_nodes_two_restricted_nodes() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_2');
    
    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Two restricted nodes test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the third case
CREATE OR REPLACE FUNCTION test_get_restricted_nodes_three_restricted_nodes() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[1, 2, 3]; -- nodes 1, 2, and 3 should be restricted
BEGIN
    PERFORM prepare_restricted_nodes_test_env(); -- Ensure table exists
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_restricted_nodes() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_3');
    
    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Three restricted nodes test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the third case
CREATE OR REPLACE FUNCTION test_get_restricted_nodes_single_bidirectional_contraction()
    RETURNS SETOF TEXT
    LANGUAGE plpgsql
AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[1, 3]; -- nodes 1, 2, and 3 should be restricted
BEGIN
    PERFORM prepare_restricted_nodes_test_env(); -- Ensure table exists
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_restricted_nodes() started';

    -- Setup test data
    PERFORM load_graphml_to_road_segments('single_bidirectional_contraction');

    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Three restricted nodes test');
END;
$$;

-- Test function for the third case
CREATE OR REPLACE FUNCTION test_get_restricted_nodes_bidirectional_and_par_edge()
    RETURNS SETOF TEXT
    LANGUAGE plpgsql
AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[1, 2, 3]; -- nodes 1, 2, and 3 should be restricted
BEGIN
    PERFORM prepare_restricted_nodes_test_env(); -- Ensure table exists
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_restricted_nodes() started';

    -- Setup test data
    PERFORM load_graphml_to_road_segments('single_bidirectional_contraction_and_parallel_edge');

    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Three restricted nodes test');
END;
$$;


CREATE OR REPLACE FUNCTION test_get_restricted_nodes_single_bidirectional_to_parallel_edge()
    RETURNS SETOF TEXT
    LANGUAGE plpgsql
AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[1, 2, 3]; -- nodes 1, 2, and 3 should be restricted
BEGIN
    PERFORM prepare_restricted_nodes_test_env(); -- Ensure table exists
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_restricted_nodes() started';

    -- Setup test data
    PERFORM load_graphml_to_road_segments('single_bidirectional_to_parallel_edge');

    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Three restricted nodes test');
END;
$$;



-- Example of running tests:
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes$'); -- runs only startup
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_three_node_chain'); -- runs the first test
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_two_restricted_nodes'); -- runs the second test
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_three_restricted_nodes'); -- runs the third test 