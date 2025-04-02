CREATE OR REPLACE FUNCTION load_graphml_to_nodes_edges(graph_name text) RETURNS VOID AS $$
DECLARE
    graph_path text;
    graph_content xml;
BEGIN
    -- Get the path to the test data
    graph_path := format('SQL/tests/data/%s.graphml', graph_name);

    -- Get the GraphML content from the database
    SELECT content INTO graph_content
    FROM public.test_graphs
    WHERE name = graph_name;

    IF graph_content IS NULL THEN
        RAISE EXCEPTION 'Graph % not found in test_graphs table', graph_name;
    END IF;

    
    -- Clear existing data
    DELETE FROM edges WHERE area = 9999;
    DELETE FROM nodes WHERE area = 9999;
    
    -- Load nodes
    INSERT INTO nodes (id, geom, area)
    SELECT 
        node_id::bigint,
        ST_SetSRID(ST_MakePoint(node_y::float, node_x::float), 4326),
        9999
    FROM XMLTABLE('//node' PASSING graph_content
        COLUMNS
            node_id text PATH '@id',
            node_x text PATH 'data[@key="d0"]/x',
            node_y text PATH 'data[@key="d0"]/y'
    );
    
    -- Load edges
    INSERT INTO edges ("from", "to", geom, area)
    SELECT 
        source_id::bigint,
        target_id::bigint,
        ST_Multi(ST_MakeLine(
            (SELECT geom FROM nodes WHERE id = source_id::bigint),
            (SELECT geom FROM nodes WHERE id = target_id::bigint)
        )),
        9999
    FROM XMLTABLE('//edge' PASSING graph_content
        COLUMNS
            source_id text PATH '@source',
            target_id text PATH '@target'
    );
    
    RAISE NOTICE 'Loaded graph % with % nodes and % edges', 
        graph_name, 
        (SELECT count(*) FROM nodes WHERE area = 9999),
        (SELECT count(*) FROM edges WHERE area = 9999);
END;
$$ LANGUAGE plpgsql; 