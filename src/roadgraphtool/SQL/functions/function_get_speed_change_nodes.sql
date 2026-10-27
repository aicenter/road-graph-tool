-- Nodes where the speed changes: nodes whose incident road segments (road_segments temporary table with the
-- speed column, see contract_graph_in_area) have more than one distinct speed.
-- These nodes must not be contracted, so that each contracted edge has a single speed.
CREATE OR REPLACE FUNCTION get_speed_change_nodes()
    RETURNS bigint[]
    LANGUAGE plpgsql
AS
$$
DECLARE
    speed_change_nodes bigint[];
BEGIN
    speed_change_nodes := (
        SELECT coalesce(array_agg(node_speeds.node_id), ARRAY[]::bigint[])
        FROM (
            SELECT incident_speeds.node_id
            FROM (
                SELECT road_segments.from_node AS node_id, road_segments.speed FROM road_segments
                UNION ALL
                SELECT road_segments.to_node AS node_id, road_segments.speed FROM road_segments
            ) AS incident_speeds
            GROUP BY incident_speeds.node_id
            HAVING count(DISTINCT incident_speeds.speed) > 1
        ) AS node_speeds
    );

    RAISE NOTICE 'Computed % speed change nodes', cardinality(speed_change_nodes);

    RETURN speed_change_nodes;
END;
$$;
