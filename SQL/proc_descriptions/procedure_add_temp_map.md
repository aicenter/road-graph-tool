# Procedure add temp map
## Purpose of this file
The puprose of this file is to ensure that there are as little misunderstandings as could be. That's why it serves to show how I (Vladyslav Zlochevskyi) see what 1st procedure does.
Also this way I might figure out what actually could be tested in this procedure.

## Description of the 1st procedure
Procedure `add_temp_map(map_area integer)`.
- Procedure's name implicates that before this procedure is executed there are some **data** already in the so-called temporary tables.
- What tables are taking part in this procedure: ways, ways_tmp, nodes, nodes_tmp, nodes_ways, nodes_ways_tmp.
- The flow of the procedure:
    1) All data that have `area` equal to given `map_area` are deleted from the so-called permanent tables such as: ways, nodes and nodes_ways.
    2) Now there is an attempt to insert new data instead, specifically data from corresponding temporary tables, which are in some way connected to `map_area`:
        - `Insert Into nodes(id, geom, area) Select osm_id, geom, map_area From nodes_tmp`. There is no filtering by `area`, which implicates that all data in nodes_tmp should contain only data related to given `map_area`. Could be the first thing to be tested? But testing is not about data, but procedure. Not sure what to do. (it also applicates to every other `insert`)
        - `Insert Into ways (id, tags, geom, "from", "to", area, oneway)`. There is a more complicated `SELECT` as it is double joined on `nodes_tmp` table. Do not really see anything, that should be tested here
        - `Insert Into nodes_ways (node_id, way_id, position, area)`. There is also a more complicated `SELECT` with double `JOIN`, but do not really see, what could be tested here. 
- Note to the flow: inserting is executed with additional specification `On Conflict Do Nothing`. The question is: is there a case, when conflict occures, it does nothing, but actually shouldn't?
<!-- - Additional question. As it was described above, this procedure should be executed only in a context that there are already some temporary data -->
- The big question is: what this procedure should do in the big picture? It is obvious it's trying to move data from temporary tables to permanent ones, but actually in what context? I think should this question be answered I would get the idea of what exactly should be tested.
<!-- - Primary Keys of tables: nodes(id), nodes_tmp(id), ways(id), ways_tmp(id), nodes_ways(id), nodes_ways_tmp(no primary key?) -->
