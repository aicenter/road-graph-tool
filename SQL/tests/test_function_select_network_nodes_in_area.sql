-- test function to select all nodes in a given area
-- TODO add tests

-- function to be tested
CREATE OR REPLACE FUNCTION select_network_nodes_in_area(area_id smallint)
RETURNS TABLE(index integer, id bigint, x float, y float, geom geometry)
LANGUAGE sql
AS
$$
SELECT
	(row_number() over () - 1)::integer AS index, -- index starts at 0
	nodes.id AS id, -- node_id
	st_x(nodes.geom) AS x, -- x coord extracted from geom
	st_y(nodes.geom) AS y, -- y coord extracted from geom
	nodes.geom as geom -- node_geom
	FROM nodes
	JOIN component_data
		ON component_data.node_id = nodes.id
		   	AND component_data.area = area_id
			AND component_data.component_id = 0
			AND nodes.contracted = FALSE
ORDER BY nodes.id;
$$;

SELECT (row_number() over () - 1)::integer as index, id as area_id, name
         FROM areas ORDER BY area_id;