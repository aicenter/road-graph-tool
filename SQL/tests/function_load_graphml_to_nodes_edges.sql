CREATE OR REPLACE FUNCTION load_graphml_to_nodes_edges(graph_name text) RETURNS VOID AS $$
DECLARE
    graph_content xml;
BEGIN
    -- Get the GraphML content from the database
    SELECT content INTO graph_content
    FROM public.test_graphs
    WHERE name = graph_name;

    IF graph_content IS NULL THEN
        RAISE EXCEPTION 'Graph % not found in test_graphs table', graph_name;
    END IF;

    -- Clear existing data
    DELETE FROM ways WHERE area = 9999;
    DELETE FROM nodes WHERE area = 9999;
    
    -- Load nodes using labels as IDs
    INSERT INTO nodes (id, geom, area)
    SELECT 
        node_label::bigint,
        ST_SetSRID(ST_MakePoint(0, 0), 4326),
        9999
    FROM XMLTABLE(
        XMLNAMESPACES(
            'http://graphml.graphdrawing.org/xmlns' AS dns,
            'http://www.yworks.com/xml/yfiles-common/3.0' AS y,
            'http://www.yworks.com/xml/yfiles-common/markup/3.0' AS x
        ),
        '//dns:node' PASSING graph_content
        COLUMNS
            node_label text PATH './/dns:data/x:List/y:Label/@Text'
    );
    
    -- Load ways using node labels as IDs
    INSERT INTO ways (id, "from", "to", geom, oneway, area)
    SELECT 
        nextval('edge_id_seq'),
        source_nodes.label::bigint,
        target_nodes.label::bigint,
        ST_Multi(ST_MakeLine(
            (SELECT geom FROM nodes WHERE id = source_nodes.label::bigint),
            (SELECT geom FROM nodes WHERE id = target_nodes.label::bigint)
        )),
        false,  -- Default to two-way
        9999
    FROM XMLTABLE(
        XMLNAMESPACES(
            'http://graphml.graphdrawing.org/xmlns' AS dns,
            'http://www.yworks.com/xml/yfiles-common/3.0' AS y,
            'http://www.yworks.com/xml/yfiles-common/markup/3.0' AS x
        ),
        '//dns:edge' PASSING graph_content
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
        '//dns:node' PASSING graph_content
        COLUMNS
            id text PATH '@id',
            label text PATH './/dns:data/x:List/y:Label/@Text'
    )) AS source_nodes ON edges.source = source_nodes.id
    JOIN (SELECT id, label FROM XMLTABLE(
        XMLNAMESPACES(
            'http://graphml.graphdrawing.org/xmlns' AS dns,
            'http://www.yworks.com/xml/yfiles-common/3.0' AS y,
            'http://www.yworks.com/xml/yfiles-common/markup/3.0' AS x
        ),
        '//dns:node' PASSING graph_content
        COLUMNS
            id text PATH '@id',
            label text PATH './/dns:data/x:List/y:Label/@Text'
    )) AS target_nodes ON edges.target = target_nodes.id;
    
    RAISE NOTICE 'Loaded graph % with % nodes and % ways', 
        graph_name, 
        (SELECT count(*) FROM nodes WHERE area = 9999),
        (SELECT count(*) FROM ways WHERE area = 9999);
END;
$$ LANGUAGE plpgsql; 