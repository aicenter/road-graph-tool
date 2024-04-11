# Get ways in target area Description
## Purpose of this file
The purpose of this file is to ensure that there are as little misunderstandings as could be. That's why it serves to show how I (Vladyslav Zlochevskyi/zlochina) see what this procedure does. Also this way I might figure out what actually could be tested in this procedure.

## Description of the function
- Function name: get_way_in_target_area
- Small description: this function is actually a helper function for a procedure `assign_average_speed_to_all_segments_in_area()`.


## Code
!!! Warning Warning
    There could be some minor changes to this block of code (such as comments or other helping lines). To see original snippet, please refer to the corresponding .sql file.
```sql
create function get_ways_in_target_area(target_area_id smallint)
    returns TABLE(id bigint, tags hstore, geom geometry, area integer, "from" bigint, "to" bigint, oneway boolean)
    language sql
as
$$
	SELECT ways.*
	        FROM ways
	            JOIN areas ON areas.id = target_area_id AND st_intersects(areas.geom, ways.geom);
$$;
```
