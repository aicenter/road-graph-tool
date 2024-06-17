# compute_speeds_for_segments Description
## Purpose of this file
The purpose of this file is to ensure that there are as little misunderstandings as could be. That's why it serves to show how I (Vladyslav Zlochevskyi/zlochina) see what this function does. Also this way I might figure out what actually could be tested in this function.

## Description of the procedure
### Procedure Name
`compute_speeds_for_segments`

### Description
The `compute_speeds_for_segments` procedure calculates speeds for a given hour and day of the week within a specified target area. 

### Input Parameters
- `target_area_id`::`smallint`: Identifier for the target area.
- `speeds_records_dataset`: Identifier for the speed records dataset.
- `hour`::`smallint`: The hour for which the speeds are being computed.
- `day_of_week`::`smallint`: The day of the week for which the speeds are being computed. 

### Returns
- This procedure does not return any values.

### Flow

1. **Create Temporary Tables**
    - **Temporary Table `target_ways`**:
        - This table is created in the same way function `get_ways_in_target_area(target_area_id smallint)` creates table.
        - An index is added to `target_ways` to optimize the search of the records.

    - **Temporary Table `node_sequences`**:
        - Structure: `(from_nodes_ways.node_id, to_node_ways.node_id, target_ways.id, from_nodes_ways.position, to_nodes_ways.position)`.
        - This table contains records indicating from which node to which node one can travel via a specific way, with additional information on the nodes' positions in a particular edge.
        - Indexes are added to this table for optimization.

2. **Main Flow**
    - **Conditional Block**:
        - **If** `day_of_week` is not provided:
            - Set `dataset_quality = 2`.
        - **Else**:
            - Set `dataset_quality = 1`.

    - **Temporary Table `grouped_speed_records`**:
        - Structure: `(from_osm_id, to_osm_id, speed, st_dev)`.
        - If `dataset_quality = 1`, data for this table is sourced from `speed_records`.
        - If `dataset_quality = 2`, data for this table is sourced from `speed_records_quarterly`.

    - **Insertion into `nodes_ways_speeds`**:
        - Use `UNION` to merge the selection of data into two groups: ascending sequences and descending sequences.
        - Insert the merged data into `nodes_ways_speeds`.

This procedure is designed to efficiently calculate and update speed records for given time parameters in a specified target area. The use of temporary tables and indexes ensures optimal performance during the data processing steps.

## TODO list
- [x] Create description of the procedure
- [x] Check if index `target_ways_id_idx` of `target_ways` is used. __Is indeed used__
- [x] Check if indexes `node_segments_osm_id_idx`, `node_segments_wf_idx`, `node_segments_wt_idx` of `node_sequences` table are used. __Only `node_segments_wf_idx` is used__ -> Issue.
- [x] Add deeper exaplanation of data selection for `grouped_speed_records` TEMP table. - No need, selection is plain.
- [ ] Reduction of TEMP tables into CTEs AKA With statements. - `target_ways` - used twice in independent contexts (first one for __STDOUT output__) + additional INDEXes, `node_sequences` - used twice in independent contexts (first one for __STDOUT output__) + 3 INDEXes, `grouped_speed_records` - same as previous two + different table sources are applied to different input of function.
- [ ] Reduction of If-else statement (1. step) with conditional WHERE clause. - Not easily achived as we have two different source for every case of dataset_quality, and refactored block with great chance would have worse perfomance. Does not worth it, in my opinion.
<!-- - [ ] Reduction of calculation of average speed in 3rd step of main flow - it is calculated twice. May influence the execution perfomance depending on the number of stored data. - Not really sure, cause window function avg() applies after finding records, not before. -->
<!-- On the other hand, im not really sure why i've brought it up -->
- [x] Humanize/formalize the description.

## QA
- Indexes `node_segments_osm_id_idx` & `node_segments_wt_idx` are not used, I think we should remove their creation queries. `RESOLVED`

## Code
!!! Warning Warning
    There could be some minor changes to this block of code (such as comments or other helping lines). To see original snippet, please refer to the corresponding .sql file.
```sql
CREATE OR REPLACE PROCEDURE compute_speeds_for_segments(target_area_id smallint, speed_records_dataset smallint, hour smallint, day_of_week smallint DEFAULT NULL::smallint)
	LANGUAGE plpgsql
AS
$$
DECLARE
	dataset_quality smallint = 1;
    current_count integer;
BEGIN

-- select ways in area
RAISE NOTICE 'Selecting ways in area: "%"', (SELECT name FROM areas WHERE id = target_area_id);

CREATE TEMPORARY TABLE target_ways AS
	(
		SELECT ways.* FROM ways JOIN areas ON areas.id = target_area_id AND st_intersects(areas.geom, ways.geom)
	);
CREATE INDEX target_ways_id_idx ON target_ways(id);

RAISE NOTICE '% ways selected', (SELECT count(1) FROM target_ways);

-- node sequences in area. Note that the from/to pairs are not necessarily unique, as the same node can appear
-- multiple times in a way (cycles)
RAISE NOTICE 'Generating node sequences in target area';
CREATE TEMPORARY TABLE node_sequences AS
(
	SELECT
		from_nodes_ways.node_id AS from_id,
		to_node_ways.node_id AS to_id,
		target_ways.id AS way_id,
		from_nodes_ways.position AS from_position,
		to_node_ways.position AS to_position
		FROM
			nodes_ways from_nodes_ways
				JOIN target_ways ON from_nodes_ways.way_id = target_ways.id
				JOIN nodes_ways to_node_ways
					 ON from_nodes_ways.way_id = to_node_ways.way_id
						 AND (
									from_nodes_ways.position < to_node_ways.position
								OR (from_nodes_ways.position > to_node_ways.position AND target_ways.oneway = false)
							)
);

-- Create index for `node_sequences` on (way_id, from_position)
CREATE INDEX node_segments_wf_idx ON node_sequences(way_id, from_position); 

RAISE NOTICE '% node sequences generated', (SELECT count(1) FROM node_sequences);

-- main flow:
--  1) if-else statement
IF day_of_week IS NULL THEN
	dataset_quality = 2;
	RAISE NOTICE 'Grouping speed records using speed dataset aggregated by hour (%). Hour %',
		(SELECT name FROM speed_datasets WHERE id = speed_records_dataset), hour;
	-- group the speed records - exact hour
	CREATE TEMPORARY TABLE grouped_speed_records AS
	(
		SELECT
			from_osm_id,
			to_osm_id,
			avg(speed_mean) as speed,
			avg(st_dev) as st_dev
			FROM
				speed_records_quarterly
			WHERE
					dataset = speed_records_dataset
				AND speed_records_quarterly.hour = compute_speeds_for_segments.hour
			GROUP BY
				from_osm_id, to_osm_id
	);
ELSE
    -- no provided _day_of_week_ => dataset_quality=1

	-- group the speed records - exact day in week and hour
	RAISE NOTICE 'Grouping speed records using exact speed dataset %. Hour %, day of week: %',
		(SELECT name FROM speed_datasets WHERE id = speed_records_dataset), hour, day_of_week;
	CREATE TEMPORARY TABLE grouped_speed_records AS
	(
		SELECT
			from_osm_id,
			to_osm_id,
			avg(speed) as speed,
			avg(st_dev) as st_dev
			FROM
				speed_records
			WHERE
					dataset = speed_records_dataset
				AND EXTRACT(HOUR FROM datetime) = hour
				AND EXTRACT(ISODOW FROM datetime) = day_of_week
			GROUP BY
				from_osm_id, to_osm_id
	);
END IF;

RAISE NOTICE '% speed records aggregated by from/to selected', (SELECT count(1) FROM grouped_speed_records);

--  2) calculate all records of `nodes_ways_speeds`
current_count = (SELECT count(1) FROM nodes_ways_speeds);
RAISE NOTICE 'Computing speeds for segments and inserting the result into nodes_ways_speeds';

--  3) execute insertion
INSERT INTO nodes_ways_speeds
(
	from_node_ways_id,
	to_node_ways_id,
	speed,
	st_dev,
	quality,
	source_records_count
)
SELECT
	from_node_ways.id AS "from",
	to_node_ways.id AS "to",
	avg(speed_records.speed) AS speed,
	avg(speed_records.st_dev) AS st_dev,
	dataset_quality,
	count(1) AS source_records_count
	FROM grouped_speed_records speed_records
			 JOIN node_sequences ns
				  ON speed_records.from_osm_id = ns.from_id
					  AND speed_records.to_osm_id = ns.to_id
					  AND from_position < to_position
			 JOIN nodes_ways from_node_ways
				  ON from_node_ways.way_id = ns.way_id
					  AND from_node_ways.position >= ns.from_position
			 JOIN nodes_ways to_node_ways
				  ON to_node_ways.way_id = ns.way_id
					  AND to_node_ways.position <= ns.to_position
					  AND to_node_ways.position = from_node_ways.position + 1
			 LEFT JOIN nodes_ways_speeds nwsr ON
					nwsr.from_node_ways_id = from_node_ways.id
				AND nwsr.to_node_ways_id = to_node_ways.id
	WHERE nwsr.from_node_ways_id IS NULL
	GROUP BY from_node_ways.id, to_node_ways.id
UNION
SELECT
	from_node_ways.id AS "from",
	to_node_ways.id AS "to",
	avg(speed_records.speed) AS speed,
	avg(speed_records.st_dev) AS st_dev,
	dataset_quality,
	count(1) AS source_records_count
	FROM grouped_speed_records speed_records
			 JOIN node_sequences ns
				  ON speed_records.from_osm_id = ns.from_id
					  AND speed_records.to_osm_id = ns.to_id
					  AND from_position > to_position
			 JOIN nodes_ways from_node_ways
				  ON from_node_ways.way_id = ns.way_id
					  AND from_node_ways.position <= ns.from_position
			 JOIN nodes_ways to_node_ways
				  ON to_node_ways.way_id = ns.way_id
					  AND to_node_ways.position >= ns.to_position
					  AND to_node_ways.position = from_node_ways.position - 1
			 LEFT JOIN nodes_ways_speeds nwsr ON
					nwsr.from_node_ways_id = from_node_ways.id
				AND nwsr.to_node_ways_id = to_node_ways.id
	WHERE nwsr.from_node_ways_id IS NULL
	GROUP BY from_node_ways.id, to_node_ways.id;

RAISE NOTICE 'Inserted speed for % node segments, quality %',
    (SELECT count(1) FROM nodes_ways_speeds) - current_count, dataset_quality;

DISCARD TEMPORARY;
END$$;
```
