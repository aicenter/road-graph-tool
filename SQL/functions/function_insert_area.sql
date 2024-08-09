------------------------------------------------------------------------------------------------------------------------
-- Function: insert_area
-- Description: This function inserts a new area into the areas table converting the geom from json to geometry
-- Parameters:
--      - id: integer
--      - name: varchar
--      - description: varchar
--      - geom: json
-- Returns: -
-- Required tables: None
-- Affected tables: areas
-- Author: Vladyslav Zlochevskyi
-- Date: 2024
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION insert_area(
    name VARCHAR,
    geom JSON,
    id INTEGER DEFAULT NULL,
    description VARCHAR DEFAULT NULL
) RETURNS VOID AS
$$
BEGIN
    IF id IS NULL THEN
        INSERT INTO areas(name, description, geom)
        VALUES (
            name,
            description,
            st_geomfromgeojson(geom)
        );
    ELSE
        INSERT INTO areas(id, name, description, geom)
        VALUES (
            id,
            name,
            description,
            st_geomfromgeojson(geom)
        );
    END IF;
END;
$$ LANGUAGE plpgsql;
