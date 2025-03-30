DROP FUNCTION IF EXISTS load_graphml_to_road_segments;
CREATE FUNCTION load_graphml_to_road_segments(graph_name text)
    RETURNS void
    LANGUAGE plpgsql
AS
$$
DECLARE
    xml_data xml;
    node_record RECORD;
    edge_record RECORD;
BEGIN
    -- Get the GraphML content from the database
    SELECT content INTO xml_data
    FROM public.test_graphs
    WHERE name = graph_name;
    
    IF xml_data IS NULL THEN
        RAISE EXCEPTION 'Graph % not found in test_graphs table', graph_name;
    END IF;

--     -- First, create nodes
--     FOR node_record IN
--         SELECT
--             (xpath('//node[@id=$1]/@id', node, ARRAY[node_id]))[1]::text as id,
--             (xpath('//node[@id=$1]/data[@key="d5"]/y:RectD/@X', node, ARRAY[node_id]))[1]::text as x,
--             (xpath('//node[@id=$1]/data[@key="d5"]/y:RectD/@Y', node, ARRAY[node_id]))[1]::text as y
--         FROM unnest(xpath('//node', xml_data)) AS node,
--         LATERAL (SELECT (xpath('@id', node))[1]::text AS node_id) AS n
--     LOOP
--         RAISE NOTICE 'Loaded node: %', node_record.id;
--         INSERT INTO nodes (id, geom)
--         VALUES (
--             node_record.id::bigint,
--             ST_SetSRID(ST_MakePoint(node_record.x::float, node_record.y::float), 4326)
--         )
--         ON CONFLICT (id) DO NOTHING;
--     END LOOP;

    -- Then, create road segments from edges
    FOR edge_record IN
        SELECT 
            (xpath('//edge[@id=$1]/@source', edge, ARRAY[edge_id]))[1]::text as source,
            (xpath('//edge[@id=$1]/@target', edge, ARRAY[edge_id]))[1]::text as target
        FROM unnest(xpath('//edge', xml_data)) AS edge,
        LATERAL (SELECT (xpath('@id', edge))[1]::text AS edge_id) AS e
    LOOP
        RAISE NOTICE 'Loaded edge: % -> %', edge_record.source, edge_record.target;
        INSERT INTO road_segments (from_node, to_node)
        VALUES (
            edge_record.source::bigint,
            edge_record.target::bigint
        )
        ON CONFLICT DO NOTHING;
    END LOOP;
END;
$$; 