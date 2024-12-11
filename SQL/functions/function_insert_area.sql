------------------------------------------------------------------------------------------------------------------------
-- Function: insert_area
-- Description: This function inserts a new area into the areas table converting the geom from json to geometry
-- Parameters:
--      - id: integer
--      - name: varchar
--      - description: varchar
--      - geom: json
-- Returns: ID of the newly inserted area: integer
-- Required tables: None
-- Affected tables: areas
-- Author: Vladyslav Zlochevskyi, David Fiedler
-- Date: 2024
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION insert_area(
    name VARCHAR,
    geom_json JSON DEFAULT NULL,
    area_id INTEGER DEFAULT NULL,
    description VARCHAR DEFAULT NULL
) RETURNS INTEGER AS
$$
DECLARE
    geom GEOMETRY;
BEGIN
    IF geom_json IS NULL THEN
        geom = NULL;
    ELSE
        geom = st_geomfromgeojson(geom_json);
    END IF;
    IF area_id IS NULL THEN
        INSERT INTO areas(name, description, geom)
        VALUES (
            name,
            description,
            geom
        )
        RETURNING id INTO area_id;
    ELSE
        INSERT INTO areas(id, name, description, geom)
        VALUES (
            id,
            name,
            description,
            geom
        )
        RETURNING id INTO area_id;
    END IF;

    RETURN area_id;
END;
$$ LANGUAGE plpgsql;
