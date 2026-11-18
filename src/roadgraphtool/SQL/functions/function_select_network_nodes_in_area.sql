------------------------------------------------------------------------------------------------------------------------
-- This function returns road network nodes in a given area: the nodes of the largest strong component of the area.
-- The components of an area contain only the nodes of the edges of that area (see compute_strong_components), so
-- the result does not depend on the other areas in the schema.
-- Parameters:
--      - area_id: The area id.
-- Returns: network nodes in the given area.
-- Required tables: nodes, component_data
-- Affected tables: None
-- Author: David Fiedler
-- Date: 2022
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION select_network_nodes_in_area(area_id smallint)
RETURNS TABLE(index integer, id bigint, x float, y float, geom geometry)
LANGUAGE sql
AS
$$
SELECT
	(row_number() over () - 1)::integer AS index,
	nodes.id AS id,
	st_x(nodes.geom) AS x,
	st_y(nodes.geom) AS y,
	nodes.geom as geom
	FROM nodes
	JOIN component_data
		ON component_data.node_id = nodes.id
		   	AND component_data.area = area_id
			AND component_data.component_id = 0
ORDER BY nodes.id;
$$