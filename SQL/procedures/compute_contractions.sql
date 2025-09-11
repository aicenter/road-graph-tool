CREATE OR REPLACE PROCEDURE compute_contractions(IN restricted_vertices bigint[])
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Computing contractions';
    CREATE TEMPORARY TABLE contractions AS (
        SELECT
            id,
            source,
            target,
            unnest(contracted_vertices) AS contracted_vertex
            FROM
                pgr_contraction(
                    'SELECT row_number() OVER () AS id, "from_node" AS source, "to_node" AS target, 0 AS cost FROM road_segments',
                    ARRAY [2],
                    forbidden_vertices => restricted_vertices
                )
    );
    CREATE INDEX contractions_index_contracted_vertex ON contractions (contracted_vertex);
    CREATE INDEX contractions_index_from_to ON contractions (source, target);
    RAISE NOTICE '% nodes contracted', (SELECT count(*) FROM contractions);
END
$$; 