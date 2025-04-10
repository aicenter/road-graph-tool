create OR REPLACE function get_ways_in_target_area(target_area_id smallint)
    returns TABLE(id bigint, tags hstore, geom geometry, area integer, "from" bigint, "to" bigint, oneway boolean)
    language plpgsql
as
$$
BEGIN
    -- raise exception if the target area does not exist
    IF NOT EXISTS (SELECT 1 FROM areas WHERE areas.id = target_area_id) THEN
        RAISE EXCEPTION 'The target area with id % does not exist', target_area_id;
    END IF;

    -- raise exception if the geometry of the target area is NULL
    IF (SELECT areas.geom IS NULL FROM areas WHERE areas.id = target_area_id) THEN
        RAISE EXCEPTION 'The target area with id % has a NULL geometry', target_area_id;
    END IF;

	RETURN QUERY SELECT ways.*
	        FROM ways
	            JOIN areas ON areas.id = target_area_id AND st_intersects(areas.geom, ways.geom);
END;
$$;

