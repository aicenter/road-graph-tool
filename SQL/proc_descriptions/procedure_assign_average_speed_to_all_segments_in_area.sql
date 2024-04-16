-- This procedure is used to assign an average speed to all segments in a specified area.
-- The average speed is calculated from nodes_ways_speeds where the quality is either 1 or 2.
-- The procedure takes two parameters:
-- target_area_id: The ID of the target area (smallint).
-- target_area_srid: The spatial reference system ID for the target area (integer).
CREATE OR REPLACE PROCEDURE assign_average_speed_to_all_segments_in_area(
	IN target_area_id smallint,
	IN target_area_srid integer
)
LANGUAGE plpgsql
AS $$
DECLARE
    -- Variable to store the number of rows affected by the last SQL command executed.
    row_count integer;
BEGIN

RAISE NOTICE 'assigning average speed to all segments in area %', (SELECT name FROM areas WHERE id = target_area_id);

-- Calculate the average speed and standard deviation from nodes_ways_speeds where the quality is either 1 or 2.
WITH average_speed AS (
	SELECT
		AVG(speed) AS average_speed,
		AVG(st_dev) AS average_st_dev,
		count(1) AS count
		FROM nodes_ways_speeds
		WHERE quality IN (1, 2)
),

-- Get all the ways in the target area.
target_ways AS (
    SELECT * FROM get_ways_in_target_area(target_area_id::smallint)
),

-- Create segments from nodes in the target ways.
node_segments AS (
	SELECT
		from_nodes_ways.id AS from_id,
		to_node_ways.id AS to_id,
		st_transform(st_makeline(from_nodes.geom, to_nodes.geom), target_area_srid::integer) AS geom
	FROM
		nodes_ways from_nodes_ways
			JOIN target_ways ON from_nodes_ways.way_id = target_ways.id
			JOIN nodes_ways to_node_ways
				 ON from_nodes_ways.way_id = to_node_ways.way_id
				 AND (
						from_nodes_ways.position = to_node_ways.position - 1
						OR (from_nodes_ways.position = to_node_ways.position + 1 AND target_ways.oneway = false)
					)
			JOIN nodes from_nodes ON from_nodes_ways.node_id = from_nodes.id
			JOIN nodes to_nodes ON to_node_ways.node_id = to_nodes.id
)
-- Insert the calculated average speed and standard deviation into nodes_ways_speeds for each segment.
-- The quality is set to 5 and the count is taken from the average_speed calculation.
-- If there is a conflict (i.e., the segment already exists in nodes_ways_speeds), do nothing.
INSERT INTO nodes_ways_speeds
SELECT
	from_id, average_speed, average_st_dev, to_id, 5 AS quality, count
FROM node_segments
	JOIN average_speed ON TRUE
ON CONFLICT DO NOTHING; -- handle overlapping areas

-- Get the number of rows affected by the last SQL command executed.
GET DIAGNOSTICS row_count = ROW_COUNT;

RAISE NOTICE 'Average speed assigned to % segments', row_count;
END;
$$


-- - Modification of __procedure__:
--     - add throwing an exception if args are invalid on the start of the procedure (invalid in this context could mean for example, that corresponding `area` does not exist, or some records referring to this area exist in one table, but do not exist in another used in this procedure). Status: `approved`
--     - add throwing an exception if `nodes_ways_speeds` table before execution contains no records. Status: `approved`
