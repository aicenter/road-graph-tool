-- Posted speed (km/h) of each way in the target area.
--
-- p_posted_speeds is an object with the keys:
--   default: speed used when no other value applies (required),
--   highway: highway tag value -> speed, used when the way has no usable maxspeed tag,
--   zones: maxspeed zone constant -> speed, see parse_maxspeed.
-- The speed is the parsed maxspeed tag, otherwise the highway default, otherwise the default speed.
-- The maxspeed and highway tags must be imported (road_import.tags).
CREATE OR REPLACE FUNCTION select_posted_way_speeds(target_area_id smallint, p_posted_speeds jsonb)
RETURNS TABLE
(
    way_id bigint,
    speed  double precision
)
LANGUAGE plpgsql
AS
$$
BEGIN
    IF p_posted_speeds IS NULL OR (p_posted_speeds ->> 'default') IS NULL THEN
        RAISE EXCEPTION 'p_posted_speeds must contain the default speed';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM tags WHERE tags."key" = 'maxspeed') THEN
        RAISE WARNING 'No maxspeed tags imported, all posted speeds are defaults. Add maxspeed to road_import.tags.';
    END IF;

    RETURN QUERY
    SELECT
        target_ways.id AS way_id,
        coalesce(
            parse_maxspeed(maxspeed_tags.tag_value, p_posted_speeds -> 'zones'),
            (p_posted_speeds -> 'highway' ->> highway_tags.tag_value)::double precision,
            (p_posted_speeds ->> 'default')::double precision
        ) AS speed
    FROM get_ways_in_target_area(target_area_id) AS target_ways
        LEFT JOIN (
            SELECT ways_tags.way_id, ways_tags.tag_value
            FROM ways_tags
                JOIN tags ON tags.id = ways_tags.tag_id AND tags."key" = 'maxspeed'
        ) AS maxspeed_tags ON maxspeed_tags.way_id = target_ways.id
        LEFT JOIN (
            SELECT ways_tags.way_id, ways_tags.tag_value
            FROM ways_tags
                JOIN tags ON tags.id = ways_tags.tag_id AND tags."key" = 'highway'
        ) AS highway_tags ON highway_tags.way_id = target_ways.id;
END;
$$;
