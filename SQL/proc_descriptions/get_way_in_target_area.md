# Get ways in target area Description
## Purpose of this file
The purpose of this file is to ensure that there are as little misunderstandings as could be. That's why it serves to show how I (Vladyslav Zlochevskyi/zlochina) see what this function does. Also this way I might figure out what actually could be tested in this function.

## Description of the function
- Function name: get_way_in_target_area
- Small description: this function is actually a helper function for a procedure `assign_average_speed_to_all_segments_in_area()`.
- The __name__ of the function + __argument__ of the function imply that this function returns a table of ways, which are based in given area.
- Input params: `target_area_id:smallint`. Return value: records with columns: `id:bigint`, `tags:hstore`, `geom:geometry`, `area:integer`, `"from":bigint`, `"to":bigint`, `oneway:boolean`
- Flow:
    - Select every column from `ways` table.
    - Inner join on `areas` table, where `area.id = target_area_id` and there is at least one intersection point of a __way__ and __area__ (this _Join_ is only for filtering out some of the records).
- __Simplifying it all__ it takes all existing ways, and filters them so that only the ones intersecting with target area would be left.

## TODO list
This part is about suggestions of what could be tested.
- [x] test that there is no record on return, when 
    - [x] 1) there is no requested area;
    - [x] 2) there is no way intersecting with area 
- [x] test that there are exact records on return, when 
    - [x] 1) there is a ways intersecting area, although there are ways, which do not intersect
- [ ] test that the function raises an error when (not sure if it is actually possible that this function would raise an error).

## QA
- Q: I see `area` column in table `ways`. Obviously it is not connected to this context (meaning that it is not target_area). Still question is what is this column responsible for? A: -

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
