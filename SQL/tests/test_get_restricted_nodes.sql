-- Test suite for get_restricted_nodes function
-- Test case 1: Simple graph with three nodes where n0 and n2 should be restricted

-- Test function for the first case
CREATE OR REPLACE FUNCTION test_get_restricted_nodes_three_node_chain() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[];
    expected_nodes bigint[] := ARRAY[0, 2]; -- n0 and n2 should be restricted
BEGIN
    RAISE NOTICE 'execution of test_get_restricted_nodes_three_node_chain() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_1');
    
    -- Get restricted nodes
    restricted_nodes := get_restricted_nodes();
    
    -- Compare results
    IF array_length(restricted_nodes, 1) != array_length(expected_nodes, 1) THEN
        RETURN NEXT fail('Number of restricted nodes does not match. Expected ' || 
            array_length(expected_nodes, 1) || ', got ' || array_length(restricted_nodes, 1));
    ELSE
        RETURN NEXT pass('Number of restricted nodes matches expected count');
    END IF;
    
    IF NOT (restricted_nodes @> expected_nodes AND expected_nodes @> restricted_nodes) THEN
        RETURN NEXT fail('Restricted nodes do not match. Expected ' || 
            array_to_string(expected_nodes, ',') || ', got ' || array_to_string(restricted_nodes, ','));
    ELSE
        RETURN NEXT pass('Restricted nodes match expected values');
    END IF;
    
    -- Cleanup
    TRUNCATE TABLE road_segments CASCADE;
    TRUNCATE TABLE nodes CASCADE;
END;
$$ LANGUAGE plpgsql;

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('_get_restricted_nodes_three_node_chain'); -- runs the test 