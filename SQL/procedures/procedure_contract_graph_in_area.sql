CREATE OR REPLACE PROCEDURE contract_graph_in_area(
    IN target_area_id smallint, IN target_area_srid integer, IN fill_speed boolean DEFAULT FALSE
)
    LANGUAGE plpgsql
AS $$
DECLARE
    non_contracted_edges_count integer;
    restricted_nodes bigint[];
BEGIN

-- road segments table
RAISE NOTICE 'Creating road segments table';
IF fill_speed THEN
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
IF fill_speed THEN
INSERT INTO edges ("from", "to", area, geom, speed)
SELECT
	max(source) AS "from",
	max(target) AS "to",
	target_area_id AS area,
	st_transform(st_multi(st_union(geom)), 4326) AS geom,
	sum(speed * st_length(geom)) / sum(st_length(geom)) AS speed
	FROM contractions
	    JOIN contraction_segments ON contraction_segments.id = contractions.id
	GROUP BY contractions.id;
ELSE
INSERT INTO edges ("from", "to", area, geom)
SELECT
    max(source) AS "from",
    max(target) AS "to",
    target_area_id AS area,
    st_transform(st_multi(st_union(geom)), 4326) AS geom
    FROM contractions
        JOIN contraction_segments ON contraction_segments.id = contractions.id
    GROUP BY contractions.id;
END IF;
RAISE NOTICE '% Edges for contracted road segments created', (SELECT count(*) FROM edges WHERE area = target_area_id) - non_contracted_edges_count;

END
$$