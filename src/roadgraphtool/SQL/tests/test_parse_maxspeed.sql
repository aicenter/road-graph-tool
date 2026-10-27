-- Test suite for parse_maxspeed function

CREATE OR REPLACE FUNCTION test_parse_maxspeed_numbers() RETURNS SETOF TEXT AS $$
BEGIN
    RETURN NEXT is(parse_maxspeed('50', NULL), 50::double precision, 'Plain number is km/h');
    RETURN NEXT is(parse_maxspeed(' 7.5 ', NULL), 7.5::double precision, 'Decimal number with spaces');
    RETURN NEXT is(parse_maxspeed('50 km/h', NULL), 50::double precision, 'Number with the km/h unit');
    RETURN NEXT is(
        round(parse_maxspeed('30 mph', NULL)::numeric, 6), 48.28032, 'Number with the mph unit is converted'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_parse_maxspeed_zones() RETURNS SETOF TEXT AS $$
DECLARE
    zone_speeds jsonb := '{"CZ:urban": 50, "CZ:living_street": 20}'::jsonb;
BEGIN
    RETURN NEXT is(parse_maxspeed('CZ:urban', zone_speeds), 50::double precision, 'Known zone constant');
    RETURN NEXT is(parse_maxspeed('CZ:rural', zone_speeds), NULL::double precision, 'Unknown zone constant');
    RETURN NEXT is(parse_maxspeed('CZ:urban', NULL), NULL::double precision, 'Zone constant without zone speeds');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_parse_maxspeed_lists() RETURNS SETOF TEXT AS $$
BEGIN
    RETURN NEXT is(parse_maxspeed('50;30', NULL), 50::double precision, 'First value of a list is used');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION test_parse_maxspeed_no_fixed_speed() RETURNS SETOF TEXT AS $$
BEGIN
    RETURN NEXT is(parse_maxspeed('none', NULL), NULL::double precision, 'none has no fixed speed');
    RETURN NEXT is(parse_maxspeed('walk', NULL), NULL::double precision, 'walk has no fixed speed');
    RETURN NEXT is(parse_maxspeed('signals', NULL), NULL::double precision, 'signals has no fixed speed');
    RETURN NEXT is(parse_maxspeed('0', NULL), NULL::double precision, 'Zero speed is rejected');
    RETURN NEXT is(parse_maxspeed('', NULL), NULL::double precision, 'Empty value');
    RETURN NEXT is(parse_maxspeed(NULL, NULL), NULL::double precision, 'NULL value');
END;
$$ LANGUAGE plpgsql;

-- Example of running tests:
-- SELECT * FROM mob_group_runtests('parse_maxspeed'); -- runs all tests
-- SELECT * FROM mob_group_runtests('parse_maxspeed_numbers'); -- runs a single test
