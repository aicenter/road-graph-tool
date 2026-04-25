--
-- Name: node_segment_data; Type: VIEW; Schema: public
--

CREATE OR REPLACE VIEW public.node_segment_data AS
 SELECT row_number() OVER () AS id,
    public.st_makeline(from_nodes.geom, to_nodes.geom) AS geom,
    nodes_ways_speeds.speed,
    nodes_ways_speeds.quality
   FROM ((((public.nodes_ways_speeds
     JOIN public.nodes_ways from_nodes_ways ON ((nodes_ways_speeds.from_node_ways_id = from_nodes_ways.id)))
     JOIN public.nodes_ways to_nodes_ways ON ((nodes_ways_speeds.to_node_ways_id = to_nodes_ways.id)))
     JOIN public.nodes from_nodes ON ((from_nodes_ways.node_id = from_nodes.id)))
     JOIN public.nodes to_nodes ON ((to_nodes_ways.node_id = to_nodes.id)));
