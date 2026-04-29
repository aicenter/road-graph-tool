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

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('_contract_graph_in_area$'); -- runs only startup
-- SELECT * FROM mob_group_runtests('_contract_graph_in_area_three_node_chain'); -- runs the first test
-- SELECT * FROM mob_group_runtests('_contract_graph_in_area_no_contraction'); -- runs the second test
-- SELECT * FROM mob_group_runtests('_contract_graph_in_area_test_3'); -- runs the third test
-- SELECT * FROM mob_group_runtests('_contract_graph_in_area_single_bidirectional_contraction'); -- runs the fourth test
-- SELECT * FROM mob_group_runtests('_contract_graph_in_area_single_bidirectional_and_parallel'); -- runs the fifth test 