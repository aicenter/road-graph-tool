-- Test suite for get_restricted_nodes function
-- Test case 1: Simple graph with three nodes where n0 and n2 should be restricted
-- Test case 2: Graph with nodes 1 and 2 as restricted nodes
-- Test case 3: Graph with nodes 1, 2, and 3 as restricted nodes

-- Startup function to create required tables
CREATE OR REPLACE FUNCTION startup_get_restricted_nodes() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of startup_get_restricted_nodes() started';
    
    -- Create temporary tables if they don't exist
    CREATE TABLE IF NOT EXISTS road_segments (
        from_node bigint NOT NULL,
        to_node bigint NOT NULL,
        PRIMARY KEY (from_node, to_node)
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
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_restricted_nodes() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_3');
    
    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();

    -- Validate results
    RETURN QUERY SELECT * FROM validate_restricted_nodes(restricted_nodes, expected_nodes, 'Three restricted nodes test');
END;
$$ LANGUAGE plpgsql;

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes$'); -- runs only startup
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_three_node_chain'); -- runs the first test
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_two_restricted_nodes'); -- runs the second test
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_three_restricted_nodes'); -- runs the third test 