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
CREATE OR REPLACE FUNCTION insert_area(integer, varchar, varchar, json) RETURNS VOID AS
$$
BEGIN
    INSERT INTO areas(id, name, description, geom) VALUES($1, $2, $3, st_geomfromgeojson($4));
END;
$$ LANGUAGE plpgsql;