create function get_ways_in_target_area(target_area_id smallint)
    returns TABLE(id bigint, tags hstore, geom geometry, area integer, "from" bigint, "to" bigint, oneway boolean)
    language sql
as
$$
	SELECT ways.*
	        FROM ways
	            JOIN areas ON areas.id = target_area_id AND st_intersects(areas.geom, ways.geom);
$$;

