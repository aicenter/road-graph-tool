-- Test suite for compute_contractions procedure
-- Test case 1: Graph with nodes 1 and 2 as restricted nodes
-- Test case 2: Graph with three nodes where node 2 should be contracted
-- Test case 3: Graph with three nodes where node 2 should be contracted

-- Renamed startup function to avoid pgtap auto-execution
CREATE OR REPLACE FUNCTION prepare_road_segments_table() RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'execution of prepare_road_segments_table() started';
    
    -- Create temporary tables if they don't exist
    CREATE TEMPORARY TABLE IF NOT EXISTS road_segments (
        from_node bigint NOT NULL,
        to_node bigint NOT NULL
    );
    
END;
$$ LANGUAGE plpgsql;

-- Shared validation function
CREATE OR REPLACE FUNCTION validate_contractions(expected_contracted_nodes bigint[], test_name text) RETURNS SETOF TEXT AS $$
DECLARE
    actual_contracted_nodes bigint[];
BEGIN
    -- Get actual contracted nodes
    SELECT ARRAY(SELECT DISTINCT contracted_vertex FROM contractions)::bigint[] INTO actual_contracted_nodes;
    
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
CREATE OR REPLACE FUNCTION test_compute_contractions_two_restricted_nodes() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[] := ARRAY[]::bigint[];
    expected_contracted_nodes bigint[] := ARRAY[]::bigint[]; -- no nodes should be contracted
BEGIN
    PERFORM prepare_road_segments_table(); -- Ensure table exists
    RAISE NOTICE 'execution of test_compute_contractions_two_restricted_nodes() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_2');
    
    -- Perform contraction
    CALL compute_contractions(restricted_nodes);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contractions(expected_contracted_nodes, 'Two restricted nodes test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the second case
CREATE OR REPLACE FUNCTION test_compute_contractions_three_node_chain() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[] := ARRAY[]::bigint[];
    expected_contracted_nodes bigint[] := ARRAY[2]; -- node 2 should be contracted
BEGIN
    PERFORM prepare_road_segments_table(); -- Ensure table exists
    RAISE NOTICE 'execution of test_compute_contractions_three_node_chain() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_1');
    
    -- Perform contraction
    CALL compute_contractions(restricted_nodes);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contractions(expected_contracted_nodes, 'Three node chain test');
END;
$$ LANGUAGE plpgsql;

-- Test function for the third case
CREATE OR REPLACE FUNCTION test_compute_contractions_three_restricted_nodes() RETURNS SETOF TEXT AS $$
DECLARE
    restricted_nodes bigint[] := ARRAY[]::bigint[];
    expected_contracted_nodes bigint[] := ARRAY[2]; -- node 2 should be contracted
BEGIN
    PERFORM prepare_road_segments_table(); -- Ensure table exists
    RAISE NOTICE 'execution of test_compute_contractions_three_restricted_nodes() started';
    
    -- Setup test data
    PERFORM load_graphml_to_road_segments('test_3');
    
    -- Perform contraction
    CALL compute_contractions(restricted_nodes);

    -- Validate results
    RETURN QUERY SELECT * FROM validate_contractions(expected_contracted_nodes, 'Three restricted nodes test');
END;
$$ LANGUAGE plpgsql;

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('_compute_contractions$'); -- runs only startup
-- SELECT * FROM mob_group_runtests('_compute_contractions_two_restricted_nodes'); -- runs the first test
-- SELECT * FROM mob_group_runtests('_compute_contractions_three_node_chain'); -- runs the second test
-- SELECT * FROM mob_group_runtests('_compute_contractions_three_restricted_nodes'); -- runs the third test 