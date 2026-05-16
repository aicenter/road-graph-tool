--
-- Procedure: wipe_road_network_data()
--
-- Truncates OSM-derived tables: nodes, ways, contracted edges, nodes_ways(_speeds),
-- tags junction rows, OSM relations, import scratch tables.
--
-- Preserves: areas, speed_datasets, speed_record_datasets, speed_records,
-- speed_records_quarterly, and the canonical tags table (empty nodes_tags / ways_tags).
--
-- WARNING: Other tables may reference nodes(id) logically (e.g. demand outside strict FK).
-- After this procedure those ids are stale unless those rows are removed or updated first.
CREATE OR REPLACE PROCEDURE wipe_road_network_data()
LANGUAGE plpgsql
AS $$
BEGIN
    SET LOCAL lock_timeout = '30s';
    SET LOCAL statement_timeout = '0';

    TRUNCATE TABLE ways, nodes RESTART IDENTITY CASCADE;

    ANALYZE areas;
    ANALYZE speed_datasets;
    ANALYZE speed_record_datasets;
    ANALYZE speed_records;
    ANALYZE speed_records_quarterly;
    ANALYZE tags;

    RAISE NOTICE 'wipe_road_network_data: road network tables truncated; areas and speed telemetry preserved.';
END;
$$;
