CREATE OR REPLACE FUNCTION get_restricted_nodes()
    RETURNS bigint[]
    LANGUAGE plpgsql
AS
$$
DECLARE
    restricted_nodes bigint[];
BEGIN
    RAISE NOTICE 'Computing restricted nodes';

    restricted_nodes := (
        SELECT array_agg(nodes.id)
        FROM nodes
            LEFT JOIN (
            -- case A: one ways to contract
            SELECT max(nodes.id) AS contract_node_id
            FROM nodes
                JOIN road_segments
                     ON nodes.id = road_segments.from_node -- fileter nodes with from edges
                JOIN road_segments AS to_road_segments ON nodes.id = to_road_segments.to_node -- filter nodes with to edges
            GROUP BY nodes.id
            HAVING count(road_segments.to_node) = 1
               AND count(to_road_segments.from_node) = 1
               AND max(road_segments.to_node) != max(to_road_segments.from_node)
            UNION
            -- case B: two ways to contract
            SELECT max(nodes.id) AS contract_node_id
            FROM nodes
                JOIN road_segments AS from_road_segments
                     ON nodes.id = from_road_segments.from_node -- fileter nodes with from edges
                JOIN road_segments AS to_road_segments
                     ON nodes.id = to_road_segments.to_node -- filter nodes with to edges
                JOIN nodes AS neighbour_nodes
                     ON neighbour_nodes.id IN (from_road_segments.to_node, to_road_segments.from_node)
            GROUP BY nodes.id
            HAVING count(DISTINCT from_road_segments.to_node) = 2
               AND count(DISTINCT to_road_segments.from_node) = 2
               AND count(DISTINCT neighbour_nodes.id) = 2
               AND count(1) = 6
        ) AS contract_nodes
                      ON nodes.id = contract_node_id
        WHERE contract_node_id IS NULL
    );

    RAISE NOTICE 'Computed % restricted nodes', array_length(restricted_nodes, 1);

    RETURN restricted_nodes;
END;
$$