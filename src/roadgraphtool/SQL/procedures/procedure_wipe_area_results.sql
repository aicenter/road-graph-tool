--
-- Procedure: wipe_area_results(target_area_id)
--
-- Deletes the results computed for one area: its strong components (component_data) and its edges.
-- Afterwards, the graph in the area can be contracted again (contract_graph_in_area, compute_strong_components).
--
-- Preserves: the area itself, the results of all other areas, and the imported road network (nodes, ways,
-- nodes_ways, tags), which is shared by all areas in the schema.
CREATE OR REPLACE PROCEDURE wipe_area_results(IN target_area_id smallint)
LANGUAGE plpgsql
AS $$
DECLARE
    component_rows integer;
    edge_rows integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM areas WHERE id = target_area_id) THEN
        RAISE EXCEPTION 'The target area with id % does not exist', target_area_id;
    END IF;

    DELETE FROM component_data WHERE area = target_area_id;
    GET DIAGNOSTICS component_rows = ROW_COUNT;

    DELETE FROM edges WHERE area = target_area_id;
    GET DIAGNOSTICS edge_rows = ROW_COUNT;

    RAISE NOTICE 'wipe_area_results: area %: % edges and % component records deleted',
        target_area_id, edge_rows, component_rows;
END;
$$;
