# Select network nodes in area Description
## Purpose of this file
The purpose of this file is to ensure that there are as little misunderstandings as could be. That's why it serves to show how I (Vladyslav Zlochevskyi/zlochina) see what this function does. Also this way I might figure out what actually could be tested in this function.

## Description of the function
- function name: select_network_nodes_in_area
- the __name of the function__ + __argument of the function__ implies that this function retrieves a series of __nodes__, which are connected in such way that they're within the given __area__.
- Input params of the function: `area_id::smallint`. Return values is a table with such columns: `index::integer`, `id::bigint`, `x::float`, `y::float`, `geom::geometry`.
- Flow:
    - retrieve records from table `nodes`;
    - join above records with table `component_data`, where col `area` equals to the arg1 and `component_id = 0` (no idea what it means), and `nodes.contracted = FALSE` (no idea what it means).
    - from given records compose new table, which contains columns:
        1) `index`. which is create by window function, so it assigns indexes to the records in range(0, count(*) - 1) including start & end;
        2) `id`. node id;
        3) `x`. Extracted from `geom` x coordinate;
        4) `y`. Extracted from `geom` y coordinate;
        5) `geom`. node geom.

## TODO list
- [ ] test that there are __no__ records in returned table, when:
    - [ ] there is no component, which corresponds to criteria mentioned in `JOIN` block.
    - [ ] there is no nodes in `area`.
- [ ] test that there are records in returned table, when there are nodes which respond to criteria.

## QA
- Q: is this function needed to the applicaton? A: -

## Code
!!! Warning Warning
    There could be some minor changes to this block of code (such as comments or other helping lines). To see original snippet, please refer to the corresponding .sql file.
```sql
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
$$
```
