CREATE OR REPLACE PROCEDURE create_edge_segments_from_contractions(IN fill_speed boolean DEFAULT FALSE)
    LANGUAGE plpgsql
AS $$
BEGIN
RAISE NOTICE 'Generating contraction segments';
IF fill_speed THEN
CREATE TEMPORARY TABLE contraction_segments AS (
    SELECT
        from_contraction.id,
        from_contraction.contracted_vertex AS from_node,
        to_contraction.contracted_vertex AS to_node,
        geom,
        speed
    FROM
        contractions from_contraction
            JOIN contractions to_contraction
                 ON from_contraction.id = to_contraction.id
            JOIN road_segments
                 ON road_segments.from_node = from_contraction.contracted_vertex
                     AND road_segments.to_node = to_contraction.contracted_vertex
    UNION
    SELECT
        id,
        source AS from_node,
        contracted_vertex AS to_node,
        geom,
        speed
    FROM contractions
             JOIN road_segments ON road_segments.from_node = source AND road_segments.to_node = contracted_vertex
    UNION
    SELECT
        id,
        contracted_vertex AS from_node,
        target AS to_node,
        geom,
        speed
    FROM contractions
             JOIN road_segments ON road_segments.from_node = contracted_vertex AND road_segments.to_node = target
);
ELSE
CREATE TEMPORARY TABLE contraction_segments AS (
    SELECT
        from_contraction.id,
        from_contraction.contracted_vertex AS from_node,
        to_contraction.contracted_vertex AS to_node,
        geom
    FROM
        contractions from_contraction
            JOIN contractions to_contraction
                 ON from_contraction.id = to_contraction.id
            JOIN road_segments
                 ON road_segments.from_node = from_contraction.contracted_vertex
                     AND road_segments.to_node = to_contraction.contracted_vertex
    UNION
    SELECT
        id,
        source AS from_node,
        contracted_vertex AS to_node,
        geom
    FROM contractions
             JOIN road_segments ON road_segments.from_node = source AND road_segments.to_node = contracted_vertex
    UNION
    SELECT
        id,
        contracted_vertex AS from_node,
        target AS to_node,
        geom
    FROM contractions
             JOIN road_segments ON road_segments.from_node = contracted_vertex AND road_segments.to_node = target
);
END IF;

RAISE NOTICE '% contraction segments generated', (SELECT count(*) FROM contraction_segments);
END
$$;