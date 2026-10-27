-- speed_source:
--   none: edges without speed,
--   fcd: speeds from floating car data (nodes_ways_speeds), contracted edges get the length-weighted mean speed,
--   posted: posted speeds (see select_posted_way_speeds, posted_speeds is its p_posted_speeds parameter).
--     Nodes where the posted speed changes are not contracted, so each edge has a single posted speed.
CREATE OR REPLACE PROCEDURE contract_graph_in_area(
    IN target_area_id smallint,
    IN target_area_srid integer,
    IN speed_source varchar DEFAULT 'none',
    IN posted_speeds jsonb DEFAULT NULL
)
    LANGUAGE plpgsql
AS $$
DECLARE
    non_contracted_edges_count integer;
    restricted_nodes bigint[];
    fill_speed boolean;
BEGIN

IF speed_source IS NULL OR speed_source NOT IN ('none', 'fcd', 'posted') THEN
    RAISE EXCEPTION 'Unsupported speed source: %. Supported: none, fcd, posted.', speed_source;
END IF;
fill_speed := speed_source <> 'none';

-- road segments table
RAISE NOTICE 'Creating road segments table';
IF speed_source = 'posted' THEN
CREATE TEMPORARY TABLE road_segments AS (
    SELECT
        node_segments.*,
        posted_way_speeds.speed
    FROM select_node_segments_in_area(target_area_id, target_area_srid) AS node_segments
        JOIN select_posted_way_speeds(target_area_id, posted_speeds) AS posted_way_speeds
            ON posted_way_speeds.way_id = node_segments.way_id
);
ELSIF speed_source = 'fcd' THEN
CREATE TEMPORARY TABLE road_segments AS (
    SELECT
    from_id,
    to_id,
    from_node,
    to_node,
    from_position,
    to_position,
    way_id,
    geom,
    nodes_ways_speeds.speed AS speed,
    nodes_ways_speeds.quality AS quality
    FROM select_node_segments_in_area(target_area_id, target_area_srid)
        JOIN nodes_ways_speeds ON
            from_id = nodes_ways_speeds.from_node_ways_id
            AND to_id = nodes_ways_speeds.to_node_ways_id
);
ELSE
    CREATE TEMPORARY TABLE road_segments AS (
    SELECT * FROM select_node_segments_in_area(target_area_id, target_area_srid)
);
end if;

CREATE INDEX road_segments_index_from_to ON road_segments (from_id, to_id);
RAISE NOTICE 'Road segments table created: % road segments', (SELECT count(*) FROM road_segments);

-- get restricted nodes
RAISE NOTICE 'Computing restricted nodes';
restricted_nodes = get_restricted_nodes();
IF speed_source = 'posted' THEN
    restricted_nodes = restricted_nodes || get_speed_change_nodes();
END IF;

-- contraction
CALL compute_contractions(restricted_nodes);

-- update nodes
RAISE NOTICE 'Updating nodes';
UPDATE nodes
	SET contracted = TRUE
WHERE id IN (
	SELECT contracted_vertex
	FROM contractions
);

-- edges for non contracted road segments
RAISE NOTICE 'Creating edges for non-contracted road segments';

IF fill_speed THEN
INSERT INTO edges ("from", "to", geom, area, speed)
SELECT
	road_segments.from_node,
	road_segments.to_node,
	st_multi(st_makeline(from_nodes.geom, to_nodes.geom)) as geom,
	target_area_id AS area,
	speed
	FROM road_segments
		JOIN nodes from_nodes ON from_nodes.id  = from_node AND from_nodes.contracted = FALSE
		JOIN nodes to_nodes ON to_nodes.id  = to_node AND to_nodes.contracted = FALSE
	JOIN ways ON ways.id = road_segments.way_id;
ELSE
INSERT INTO edges ("from", "to", geom, area)
SELECT
    road_segments.from_node,
    road_segments.to_node,
    st_multi(st_makeline(from_nodes.geom, to_nodes.geom)) as geom,
    target_area_id AS area
    FROM road_segments
        JOIN nodes from_nodes ON from_nodes.id  = from_node AND from_nodes.contracted = FALSE
        JOIN nodes to_nodes ON to_nodes.id  = to_node AND to_nodes.contracted = FALSE
        JOIN ways ON ways.id = road_segments.way_id;
END IF;

non_contracted_edges_count := (SELECT count(*) FROM edges WHERE area = target_area_id);
RAISE NOTICE '% Edges for non-contracted road segments created', non_contracted_edges_count;

-- contraction segments generation
CALL create_edge_segments_from_contractions(fill_speed);

-- edges for contracted road segments
RAISE NOTICE 'Creating edges for contracted road segments';
IF speed_source = 'posted' THEN
    -- speed change nodes are not contracted, so all segments of a contraction have the same speed
    IF EXISTS (SELECT 1 FROM contraction_segments GROUP BY id HAVING min(speed) <> max(speed)) THEN
        RAISE EXCEPTION 'Some contractions span a posted speed change';
    END IF;
    INSERT INTO edges ("from", "to", area, geom, speed)
    SELECT
        max(edge_from),
        max(edge_to),
        target_area_id AS area,
        st_transform(st_multi(st_union(geom)), 4326) AS geom,
        max(speed) AS speed
    FROM contraction_segments
    GROUP BY id;
ELSIF fill_speed THEN
    INSERT INTO edges ("from", "to", area, geom, speed)
    SELECT
        max(edge_from),
        max(edge_to),
        target_area_id AS area,
        st_transform(st_multi(st_union(geom)), 4326) AS geom,
        sum(speed * st_length(geom)) / sum(st_length(geom)) AS speed
    FROM contraction_segments
    GROUP BY id;
ELSE
    INSERT INTO edges ("from", "to", area, geom)
    SELECT
        max(edge_from),
        max(edge_to),
        target_area_id AS area,
        st_transform(st_multi(st_union(geom)), 4326) AS geom
    FROM contraction_segments
    GROUP BY id;
END IF;
RAISE NOTICE '% Edges for contracted road segments created', (SELECT count(*) FROM edges WHERE area = target_area_id) - non_contracted_edges_count;

END
$$