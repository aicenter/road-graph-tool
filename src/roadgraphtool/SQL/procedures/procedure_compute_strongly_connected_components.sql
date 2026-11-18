-- Computes the strong components of the edges of the target area (edges.area) and stores them in component_data.
-- Only the edges generated for the target area are used, so the edges of other areas in the schema, including
-- overlapping ones, have no effect.
-- An area that already has components is not computed again, see wipe_area_results.
CREATE OR REPLACE PROCEDURE compute_strong_components(IN target_area_id smallint)
LANGUAGE plpgsql
AS $$
BEGIN

IF NOT EXISTS (SELECT 1 FROM areas WHERE id = target_area_id) THEN
    RAISE EXCEPTION 'The target area with id % does not exist', target_area_id;
END IF;

IF NOT EXISTS (SELECT 1 FROM edges WHERE area = target_area_id) THEN
    RAISE EXCEPTION 'Area % has no edges. Contract the graph in the area first.', target_area_id;
END IF;

IF EXISTS (SELECT 1 FROM component_data WHERE area = target_area_id) THEN
    RAISE EXCEPTION
        'Area % already has strong components. To compute them again, remove them first with wipe_area_results.',
        target_area_id;
END IF;

RAISE NOTICE 'Computing strong components for area %', (SELECT name FROM areas WHERE id = target_area_id);
CREATE TEMPORARY TABLE components AS
SELECT * FROM
pgr_strongcomponents(format(
    'SELECT row_number() OVER () AS id, "from" AS source, "to" AS target, 0 AS cost, -1 AS reverse_cost ' ||
    'FROM edges WHERE edges.area = %L', target_area_id
));
RAISE NOTICE 'Strong components computed: % components', (SELECT count(1) OVER () FROM components GROUP BY component LIMIT 1);

RAISE NOTICE 'Storing the results in the component_data table';
WITH agg AS (
	SELECT
		component,
		count(1),
		row_number() OVER (ORDER BY count(1) DESC) - 1 AS id
	FROM
		 components
	GROUP BY component
	ORDER BY count(1) DESC
)
INSERT INTO component_data
SELECT
    id,
    node,
    target_area_id
FROM
    components
	JOIN agg ON components.component = agg.component
	ORDER BY id;

DROP TABLE components;
END
$$
