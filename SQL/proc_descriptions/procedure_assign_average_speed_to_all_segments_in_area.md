# Assign average speed to all segments in area Decsription
## Purpose of this file
The purpose of this file is to ensure that there are as little misunderstandings as could be. That's why it serves to show how I (Vladyslav Zlochevskyi/zlochina) see what this procedure does. Also this way I might figure out what actually could be tested in this procedure.

## Decsription of the procedure
- Procedure name: procedure_assign_average_speed_to_all_segments_in_area
- The __name__ of the procedure + __arguments__ of the procedure implicate computing average speed per segment of an area and adding this speed info to corresponding tables.
- Input params: `target_area_id:smallint`, `target_area_srid:integer`. Return value: _None_.
- Target of the procedure: gather some info and insert it into table `nodes_ways_speeds`
- Flow:
    - Prepare for final insertion to `nodes_ways_speeds`, by executing CTE such as `average_speed`, `target_ways` and `node_segments`:
        - CTE `average_speed` aggregates all records from `nodes_ways_speeds` table to one record containing average speed and standard deviation filtered by quality either equal to 1 or 2.
        - CTE `target_ways` executes function `get_ways_in_target_area`, which returns table used by `node_segments` CTE. Note: Did not figure out the role it demonstrates to the procedure.
        - CTE `node_segments` returns a list of records with columns `from_id`, `to_id`, `geom`. `geom` column is not used afterwards, `from_id` and `to_id` are gathered from `nodes_ways` table, where the latter is joined by some specific filtering. Note: more on QA
    - Final insertion is made by a list, which is created by Cross Join aka Cartesian product of `node_segments` and `average_speed`, which actually leaves dimensionality to (`count(*) FROM node_segments` X 1), because of one line from `average_speed`. Isertion into `nodes_ways_speeds` with `quality`=5 is executed on the end.
- __Simplifying it all__, it takes records from `nodes_ways` table, adds some additional data from the same table, then adds additional columns such as `average_speed` & `average_st_dev` and inserts to `nodes_ways_speeds` with `quality`=5.

## Testing points
This part is about suggestions of what could be tested. To be added shortly afterwards

## QA
- Q: Not sure what __segment__ in this particular context means. I see that we work with the so-called __ways__, does segment refer to that. A: -
- Q: do not really think that it will matter, but anyway we seem to use column `quality` from `nodes_ways_speeds` in this procedure. We gather info on average speed/std deviation from records with quality 1 or 2, and then inserting in the same table with quality 5. A: -
- Q: Column `geom` from CTE `node_segments` is not used. Why is that? A: -
- Q: Join `JOIN target_ways ON from_nodes_ways.way_id = target_ways.id` is not used, which makes CTE `target_ways` useless. Why is that? A: -
- Q: Next block feels important, but not really sure what it filters: 
```sql
			JOIN nodes_ways to_node_ways
				 ON from_nodes_ways.way_id = to_node_ways.way_id
				 AND (
						from_nodes_ways.position = to_node_ways.position - 1
						OR (from_nodes_ways.position = to_node_ways.position + 1 AND target_ways.oneway = false)
					)
```
A: -

## Code
!!! Warning Warning
    There could be some minor changes to this block of code (such as comments or other helping lines). To see original snippet, please refer to the corresponding .sql file.
```sql
CREATE OR REPLACE PROCEDURE assign_average_speed_to_all_segments_in_area(
	IN target_area_id smallint,
	IN target_area_srid integer
)
LANGUAGE plpgsql
AS $$
DECLARE
    row_count integer;
BEGIN

RAISE NOTICE 'assigning average speed to all segments in area %', (SELECT name FROM areas WHERE id = target_area_id);

-- Declaring 3 common table expression aka CTE
-- 1. average_speed: get average speed and standard deviation (from nodes_ways_speeds table)
-- 2. target_ways: get ways in target area (id bigint, tags hstore, geom geometry, area integer, "from" bigint, "to" bigint, oneway boolean)
-- 3. node_segments: get node segments (from_id, to_id) in target area
WITH average_speed AS ( -- gather average speed and average standard deviation from nodes_ways_speeds(quality = 1, 2)
	SELECT
		AVG(speed) AS average_speed,
		AVG(st_dev) AS average_st_dev,
		count(1) AS count
		FROM nodes_ways_speeds
		WHERE quality IN (1, 2)
),
target_ways AS ( -- get ways in target area (returns a table made of areas, ways)
    SELECT * FROM get_ways_in_target_area(target_area_id::smallint)
),
node_segments AS (
	SELECT
		from_nodes_ways.id AS from_id,
		to_node_ways.id AS to_id,
		st_transform(st_makeline(from_nodes.geom, to_nodes.geom), target_area_srid::integer) AS geom -- not used !!!
	FROM
		nodes_ways from_nodes_ways
			JOIN target_ways ON from_nodes_ways.way_id = target_ways.id -- join not used !!!
			JOIN nodes_ways to_node_ways
				 ON from_nodes_ways.way_id = to_node_ways.way_id -- it takes the same record and filters on it??
				 AND (
						from_nodes_ways.position = to_node_ways.position - 1
						OR (from_nodes_ways.position = to_node_ways.position + 1 AND target_ways.oneway = false)
					)
			JOIN nodes from_nodes ON from_nodes_ways.node_id = from_nodes.id -- to gather geom
			JOIN nodes to_nodes ON to_node_ways.node_id = to_nodes.id -- to gather geom
)

INSERT INTO nodes_ways_speeds
SELECT
	from_id, average_speed, average_st_dev, to_id, 5 AS quality, count -- from_nodes.from_id, average_speed.average_speed,
                                                                        -- average_speed.average_st_dev, to_nodes.to_id, count=1
FROM node_segments
	JOIN average_speed ON TRUE
ON CONFLICT DO NOTHING; -- handle overlapping areas
-- Possible conflict: no conflict on foreign key constraints (nodes_ways_speeds_nodes_ways_id_fk/2),
-- as they're taken from the same table to which the reference is made.
-- primary key constraint (nodes_ways_speeds_pk), conflict could happen if the same segment is inserted twice


GET DIAGNOSTICS row_count = ROW_COUNT;
RAISE NOTICE 'Average speed assigned to % segments', row_count;
END;
$$;```
