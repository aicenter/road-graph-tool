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

--     RAISE NOTICE 'XML content: %', xml_data;
    -- create nodes
    FOR node_record IN
        SELECT id, label
        FROM XMLTABLE(
            XMLNAMESPACES(
                'http://graphml.graphdrawing.org/xmlns' AS dns,
                'http://www.yworks.com/xml/yfiles-common/3.0' AS y,
                'http://www.yworks.com/xml/yfiles-common/markup/3.0' AS x
            ),
            '//dns:node' PASSING xml_data
            COLUMNS
                id text PATH '@id',
                label text PATH './/dns:data/x:List/y:Label/@Text'
        ) AS nodes
    LOOP
        RAISE NOTICE 'Loaded node: %', node_record.label;
        INSERT INTO nodes (id, geom)
        VALUES (
            node_record.label::bigint,
            ST_MakePoint(0, 0)
        )
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- create road segments from edges
    FOR edge_record IN
        SELECT source,
            source_nodes.label AS source_label,
            target,
            target_nodes.label AS target_label
        FROM XMLTABLE(
                XMLNAMESPACES('http://graphml.graphdrawing.org/xmlns' AS dns,
                    'http://www.yworks.com/xml/yfiles-common/3.0' AS y
                    ),
                '//dns:edge' PASSING xml_data
                COLUMNS
                    source text PATH '@source',
                    target text PATH '@target'
             ) AS edges
            JOIN (SELECT id, label FROM XMLTABLE(
                XMLNAMESPACES(
                    'http://graphml.graphdrawing.org/xmlns' AS dns,
                    'http://www.yworks.com/xml/yfiles-common/3.0' AS y,
                    'http://www.yworks.com/xml/yfiles-common/markup/3.0' AS x
                    ),
                '//dns:node' PASSING xml_data
                COLUMNS
                    id text PATH '@id',
                    label text PATH './/dns:data/x:List/y:Label/@Text'
                                        )) AS source_nodes
                 ON edges.source = source_nodes.id
            JOIN (SELECT id, label FROM XMLTABLE(
                XMLNAMESPACES(
                    'http://graphml.graphdrawing.org/xmlns' AS dns,
                    'http://www.yworks.com/xml/yfiles-common/3.0' AS y,
                    'http://www.yworks.com/xml/yfiles-common/markup/3.0' AS x
                    ),
                '//dns:node' PASSING xml_data
                COLUMNS
                    id text PATH '@id',
                    label text PATH './/dns:data/x:List/y:Label/@Text'
                                        )) AS target_nodes
                 ON edges.target = target_nodes.id
    LOOP
        RAISE NOTICE 'Loaded edge: % -> %', edge_record.source_label, edge_record.target_label;
        INSERT INTO road_segments (from_node, to_node)
        VALUES (
            edge_record.source_label::bigint,
            edge_record.target_label::bigint
        );
    END LOOP;
END;
$$; 