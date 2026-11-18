-- speed_source:
--   none: edges without speed,
--   fcd: speeds from floating car data (nodes_ways_speeds), contracted edges get the length-weighted mean speed,
--   posted: posted speeds (see select_posted_way_speeds, posted_speeds is its p_posted_speeds parameter).
--     Nodes where the posted speed changes are not contracted, so each edge has a single posted speed.
--
-- The contraction is computed for the target area only and stored in the edges of this area (edges.area), so the
-- contractions of other areas in the schema, including overlapping ones, are neither read nor changed.
-- An area that already has edges is not contracted again, see wipe_area_results.
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

IF EXISTS (SELECT 1 FROM edges WHERE area = target_area_id) THEN
    RAISE EXCEPTION 'Area % already has edges. To contract it again, remove them first with wipe_area_results.',
        target_area_id;
END IF;

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
IF NOT EXISTS (SELECT 1 FROM road_segments) THEN
    RAISE EXCEPTION 'No road segments in area %', target_area_id;
END IF;

-- get restricted nodes
RAISE NOTICE 'Computing restricted nodes';
restricted_nodes = get_restricted_nodes();
IF speed_source = 'posted' THEN
    restricted_nodes = restricted_nodes || get_speed_change_nodes();
END IF;

-- contraction
CALL compute_contractions(restricted_nodes);

-- edges for non contracted road segments: neither of the two nodes was contracted
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
		JOIN nodes from_nodes ON from_nodes.id  = from_node
		JOIN nodes to_nodes ON to_nodes.id  = to_node
	JOIN ways ON ways.id = road_segments.way_id
	WHERE NOT EXISTS (
		SELECT 1 FROM contractions WHERE contractions.contracted_vertex IN (road_segments.from_node, road_segments.to_node)
	);
ELSE
INSERT INTO edges ("from", "to", geom, area)
SELECT
    road_segments.from_node,
    road_segments.to_node,
    st_multi(st_makeline(from_nodes.geom, to_nodes.geom)) as geom,
    target_area_id AS area
    FROM road_segments
        JOIN nodes from_nodes ON from_nodes.id  = from_node
        JOIN nodes to_nodes ON to_nodes.id  = to_node
        JOIN ways ON ways.id = road_segments.way_id
    WHERE NOT EXISTS (
        SELECT 1 FROM contractions WHERE contractions.contracted_vertex IN (road_segments.from_node, road_segments.to_node)
    );
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

-- the temporary tables are dropped, so that another area can be contracted in the same session
DROP TABLE road_segments;
DROP TABLE contractions;
DROP TABLE contraction_segments;

END
$$