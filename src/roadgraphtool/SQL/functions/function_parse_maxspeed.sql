-- Parses the value of the OSM maxspeed tag to km/h.
--
-- Supported formats: a number (km/h), a number with the km/h or mph unit, and a zone constant (country code and
-- zone type, e.g., the Czech urban zone) looked up in p_zone_speeds (zone constant -> speed in km/h).
-- For multiple values separated by a semicolon, the first one is used.
-- Returns NULL for values without a fixed speed (none, walk, signals, variable, ...), unknown zone constants,
-- and unparseable or non-positive values.
CREATE OR REPLACE FUNCTION parse_maxspeed(p_value varchar, p_zone_speeds jsonb)
RETURNS double precision
LANGUAGE plpgsql
IMMUTABLE
AS
$$
DECLARE
    first_value text := btrim(split_part(p_value, ';', 1));
    speed_match text[];
    speed double precision;
BEGIN
    IF first_value IS NULL OR first_value = '' THEN
        RETURN NULL;
    END IF;

    IF position(':' IN first_value) > 0 THEN
        speed := (p_zone_speeds ->> first_value)::double precision;
    ELSE
        speed_match := regexp_match(lower(first_value), '^([0-9]+(?:\.[0-9]+)?)\s*(km/h|kmh|kph|mph)?$');
        IF speed_match IS NULL THEN
            RETURN NULL;
        END IF;
        speed := speed_match[1]::double precision;
        IF speed_match[2] = 'mph' THEN
            speed := speed * 1.609344;
        END IF;
    END IF;

    IF speed <= 0 THEN
        RETURN NULL;
    END IF;
    RETURN speed;
END;
$$;
