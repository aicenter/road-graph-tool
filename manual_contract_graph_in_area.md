

## **Procedure: contract_graph_in_area.sql**


### **Purpose:**

This procedure optimizes road network data within a specific area by contracting the graph representation of the road network and generating optimized edge data.


### **Inputs:**



* `target_area_id`: A small integer representing the target geographical area ID.
* `target_area_srid`: An integer representing the spatial reference identifier for the target geographical area.


### **Operations:**



1. Create Temporary Table `road_segments`:
    * This operation selects road segment data within the specified geographical area using the `select_node_segments_in_area` function and creates a temporary table named `road_segments`.
    * The road segments are filtered based on the `target_area_id` and `target_area_srid` parameters.
    * An index named `road_segments_index_from_to` is created on the `from_id` and `to_id` columns of the `road_segments` table to optimize query performance.
2. Contract Graph:
    * This operation contracts the graph representation of the road network using the `pgr_contraction` function.
    * The contracted vertices are stored in a temporary table named `contractions`, along with their corresponding source and target nodes.
    * Another index named `contractions_index_contracted_vertex` is created on the `contracted_vertex` column of the `contractions` table for efficient retrieval of contracted vertices.
3. Update Nodes:
    * This operation updates the `nodes` table, marking nodes as contracted where their IDs match the contracted vertices stored in the `contractions` table.
4. Create Edges for Non-contracted Road Segments:
    * This operation generates edge data for non-contracted road segments by joining the `road_segments` table with the `nodes` table to retrieve geometry and other attributes.
    * The resulting edge data is inserted into the `edges` table, which represents the road network.
5. Generate Contraction Segments:
    * This operation generates contraction segments based on the contracted graph representation stored in the `contractions` table.
    * Contraction segments represent aggregated road segments between contracted nodes.
    * The generated segments are stored in a temporary table named `contraction_segments`.
6. Create Edges for Contracted Road Segments:
    * This operation generates edge data for contracted road segments by aggregating contraction segments and calculating average speed.
    * The resulting edge data is inserted into the `edges` table, complementing the existing edge data for non-contracted segments.


### **Outputs:**



* The procedure updates the `nodes` table to mark contracted nodes.
* Edge data for both contracted and non-contracted road segments is inserted into the `edges` table, providing an optimized representation of the road network within the specified geographical area.


### **Usage:**



* Call the procedure with appropriate values for `target_area_id` and `target_area_srid` to process road segment data and optimize the graph representation of the road network.


### **Example:**


```
call public.contract_graph_in_area(Cast(0 As smallint), 0);	
```


or


```
call public.contract_graph_in_area(target_area_id := Cast(0 As smallint), target_area_srid := 0);
```

![procedure_contract_graph_in_area](https://github.com/aicenter/road-graph-tool/assets/25695606/8de0fd29-6500-4a13-a3c1-31b57f864c65)
