
## **SQL Function Manual: select_network_nodes_in_area**

### **Overview**
The `select_network_nodes_in_area` function is designed to retrieve network nodes within a specified geographic area. It returns a table containing information about the nodes such as their index, ID, coordinates, and geometry.

### **Parameters**
* `area_id`: A small integer representing the ID of the area for which network nodes are to be selected.

### **Return Type**
The function returns a table with the following columns ordered by id:

* `index`: An integer representing the index of the node.
* `id`: A bigint representing the ID of the node.
* `x`: A double precision value representing the x-coordinate of the node.
* `y`: A double precision value representing the y-coordinate of the node.
* `geom`: A geometry object representing the geometry of the node.

### **Example**
```SELECT * FROM select_network_nodes_in_area(Cast(5 As smallint));```
