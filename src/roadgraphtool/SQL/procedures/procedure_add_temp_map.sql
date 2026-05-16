CREATE OR REPLACE PROCEDURE add_temp_map(map_area integer)
	LANGUAGE plpgsql
AS
$$BEGIN
    DELETE FROM ways WHERE area = map_area;
    DELETE FROM nodes WHERE area = map_area;
	DELETE FROM nodes_ways WHERE area = map_area;
    INSERT INTO nodes (id, geom, area) SELECT osm_id, geom, map_area FROM nodes_tmp ON CONFLICT DO NOTHING;
	INSERT INTO ways (id, geom, "from", "to", area, oneway)
		SELECT ways_tmp.osm_id, ways_tmp.geom, from_nodes.osm_id, to_nodes.osm_id, map_area, oneway FROM ways_tmp
    	JOIN nodes_tmp from_nodes ON ways_tmp."from" = from_nodes.id
    	JOIN nodes_tmp to_nodes ON ways_tmp."to" = to_nodes.id
    	ON CONFLICT DO NOTHING;
    INSERT INTO tags ("key")
        SELECT DISTINCT each_tags."key"
        FROM ways_tmp
            CROSS JOIN LATERAL each(ways_tmp.tags) AS each_tags("key", value)
        ON CONFLICT ("key") DO NOTHING;
    INSERT INTO ways_tags (way_id, tag_id, tag_value)
        SELECT ways_tmp.osm_id, tags.id, each_tags.value
        FROM ways_tmp
            CROSS JOIN LATERAL each(ways_tmp.tags) AS each_tags("key", value)
            JOIN tags ON tags."key" = each_tags."key"
            JOIN ways ON ways.id = ways_tmp.osm_id
        WHERE ways.area = map_area
        ON CONFLICT (way_id, tag_id) DO UPDATE
            SET tag_value = EXCLUDED.tag_value;
    INSERT INTO nodes_ways (node_id, way_id, position, area) 
    	SELECT nodes_tmp.osm_id, ways_tmp.osm_id, position, map_area FROM nodes_ways_tmp
    	JOIN nodes_tmp ON nodes_ways_tmp.node_id = nodes_tmp.id
    	JOIN ways_tmp ON nodes_ways_tmp.way_id = ways_tmp.id
    	ON CONFLICT DO NOTHING;
END$$;

