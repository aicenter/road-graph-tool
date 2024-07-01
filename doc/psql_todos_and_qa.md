# TODOs and QAs for PostgreSQL Functions & Procedures

## get_ways_in_target_area

### TODO List
- [x] Test that there is no record on return when:
  - [x] There is no requested area
  - [x] There is no way intersecting with area
- [x] Test that there are exact records on return when:
  - [x] There are ways intersecting the area, although there are ways which do not intersect
- [ ] Test that the function raises an error when (not sure if it is actually possible that this function would raise an error)

### QA
Q: I see `area` column in table `ways`. Obviously it is not connected to this context (meaning that it is not target_area). Still question is what is this column responsible for?
A: It is not responsible for anything in this particular context.

Thank you for providing the information for the second procedure. I'll add this to our `todos-and-qa.md` file. Here's the updated content:

## assign_average_speed_to_all_segments_in_area

### TODO List
- Testing procedure:
  - [x] Test that after execution of this procedure, some records were added to `nodes_ways_speeds` with corresponding values (which would be hardcoded to the assertion).
    Note: Multiple such tests needed, testing both segments with matching speeds, without them and the combination of segments with and without matching speeds in one way.
  - [x] Test that after double execution with the same args, records wouldn't be added second time.
  - [x] Test that after inserting invalid args (either of them), the procedure wouldn't modify table, but throw an exception.
  - [x] Test `get_ways_in_target_area()` as an individual function (independently from testing this procedure).

- Modification of procedure:
  - [x] Add throwing an exception if args are invalid on the start of the procedure.
    Note: Implemented throwing only for an invalid area id.
  - [x] Add throwing an exception if `nodes_ways_speeds` table before execution contains no records.
  - [ ] Get rid of `geom` column from CTE `node_segments`. Status: rejected

### QA
Q: Not sure what __segment__ in this particular context means. I see that we work with the so-called __ways__, does segment refer to that?
A: A segment is part of a way. Each osm way is composed of nodes. A segment is a line between two points in a way. Apart from ways and segments, there are also edges, which represent arcs in the final roadgraph. We should probably cover this notation in the readme at some point.

Q: Do we really need to use column `quality` from `nodes_ways_speeds` in this procedure? We gather info on average speed/std deviation from records with quality 1 or 2, and then inserting in the same table with quality 5.
A: The quality should be derived from the quality of the sources (worst source among all segments). But it does not matter so far as we do not use the quality anywhere...

Q: Column `geom` from CTE `node_segments` is not used. Why is that?
A: There is no obvious reason. It might be better to get rid of it in that case.

Q: Join `JOIN target_ways ON from_nodes_ways.way_id = target_ways.id` is not used, which makes CTE `target_ways` useless. Why is that?
A: Most likely, it is used to limit the segments to target ways.

Q: Can you explain this block of code:
```sql
JOIN nodes_ways to_node_ways
     ON from_nodes_ways.way_id = to_node_ways.way_id
     AND (
            from_nodes_ways.position = to_node_ways.position - 1
            OR (from_nodes_ways.position = to_node_ways.position + 1 AND target_ways.oneway = false)
        )
```
A: This join takes the records from the same table nodes_ways, matches it with way_id records and takes the ones which are either one position lower than the i-th record or one position higher (in this case it is further filtered by oneway = false).

Q: Since we're not using `quality` anymore, shouldn't we modify the procedure not to use this column anymore?
A: Quality should be left with no adjustments.

## compute_speeds_for_segments

### TODO List
- [x] Create description of the procedure
- [x] Check if index `target_ways_id_idx` of `target_ways` is used. __Is indeed used__
- [x] Check if indexes `node_segments_osm_id_idx`, `node_segments_wf_idx`, `node_segments_wt_idx` of `node_sequences` table are used. __Only `node_segments_wf_idx` is used__ -> Issue.
- [x] Add deeper explanation of data selection for `grouped_speed_records` TEMP table. - No need, selection is plain.
- [ ] Reduction of TEMP tables into CTEs AKA With statements. - `target_ways` - used twice in independent contexts (first one for __STDOUT output__) + additional INDEXes, `node_sequences` - used twice in independent contexts (first one for __STDOUT output__) + 3 INDEXes, `grouped_speed_records` - same as previous two + different table sources are applied to different input of function.
- [ ] Reduction of If-else statement (1. step) with conditional WHERE clause. - Not easily achieved as we have two different sources for every case of dataset_quality, and refactored block with great chance would have worse performance. Does not worth it, in my opinion.
- [x] Humanize/formalize the description.

### QA
Q: Indexes `node_segments_osm_id_idx` & `node_segments_wt_idx` are not used, should we remove their creation queries?

## procedure_compute_speeds_from_neighborhood_segments

### Todo list
- [x] Check why __materialized view__ `target_ways` is created, check it out
- [x] check if index `target_ways_geom_idx` is used. IS USED
- [x] check if indexes `node_segments_osm_id_idx` and `node_segments_geom_idx` are used:
    - [x] `node_segments_osm_id_idx`. IS NOT USED
    - [x] `node_segments_geom_idx`. IS USED
- [x] Humanize/formalize the description of the procedure

### QA
- Q: Why `EXECUTE format('...')` is used? Im not really seeing the need in that - A: Leftover from debugging. `RESOLVED`. **UPD** The reason why is due to `[0A000] ERROR: materialized views may not be defined using bound parameter`
- Q: Point 5.1 is reduceable to a value stored in some variable. Any need in create view? (The only assumption is that's leftover after debugging). - A: Usage of view prevents repeated usage of the same block of code to calculate the assigned segments count.
- Q: Refresh of views kinda stinks (We're not updating `node_segments` after creation) (The reason may be that there could be concurrent modification of the table, but this function is supposed to run isolated, that's why im not sure why its here). - A: I guess everything comes down to `WHERE nodes_ways_speeds.to_node_ways_id IS NULL` clause in `node_segments` view creation query. Every time we refresh after insertion to `nodes_ways_speeds`, we basically remove those records from `node_segments`, which were used to add to the target table.
- Q: `node_segments_osm_id_idx` looks like is not used at all. We may consider removing creation of this index. - A: `RESOLVED`
- Q: I've got to ask what is the relation between `target_area_id` and `target_area_srid`. I think there is indeed a strong connection between those values, that's why we may need to test the case when we pass unrelated values to this procedure (in which case it should throw an error or do nothing at all. Error would more informative to the User). - A: there is a weak connection instead, which is up to User.
- Q: In case we would want to implement the 1st test case in such way, that it would check for throwing, may I modify original procedure to throw such error (basically the same as we did with some of the previous procedures/functions)? - A: Yup


