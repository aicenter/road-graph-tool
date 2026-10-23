import {MapLibreMap, Marker, NavigationControl, ScaleControl, addProtocol} from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.12.0/dist/maplibre-gl.mjs";
import {Protocol} from "https://cdn.jsdelivr.net/npm/pmtiles@4.5.0/+esm";
import {Graph} from "./routing.js";

const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
// zoom from which the route is shown only by the highlighted edges; below, the tiles may not contain all edges
const ROUTE_DETAIL_MIN_ZOOM = 14;
const NODES_MIN_ZOOM = 13;

const routeElement = document.getElementById("route");
const hoverElement = document.getElementById("hover");

const numberFormat = new Intl.NumberFormat("en", {maximumFractionDigits: 1});

function dataUrl(fileName, buildId) {
    return new URL(`${fileName}?v=${buildId}`, window.location.href).href;
}

function renderList(element, entries) {
    const list = document.createElement("dl");
    for (const [name, value] of entries) {
        const term = document.createElement("dt");
        term.textContent = name;
        const description = document.createElement("dd");
        description.textContent = value;
        list.append(term, description);
    }
    element.replaceChildren(list);
}

function renderMessage(element, message, isError = false) {
    element.textContent = message;
    element.classList.toggle("error", isError);
}

function formatLength(meters) {
    return `${numberFormat.format(meters)} m`;
}

async function loadGraph(build) {
    const response = await fetch(dataUrl("graph.bin", build.build_id));
    if (!response.ok) {
        throw new Error(`Failed to load graph.bin: ${response.status}`);
    }
    return new Graph(await response.arrayBuffer(), build.node_count, build.edge_count);
}

function addNetworkLayers(map, build) {
    map.addSource("edges", {type: "vector", url: `pmtiles://${dataUrl("edges.pmtiles", build.build_id)}`});
    map.addSource("nodes", {type: "vector", url: `pmtiles://${dataUrl("nodes.pmtiles", build.build_id)}`});
    map.addSource("route-line", {type: "geojson", data: {type: "FeatureCollection", features: []}});

    const lineWidth = (base) => ["interpolate", ["linear"], ["zoom"], 10, base * 0.5, 16, base * 2.5];
    map.addLayer({
        id: "edges",
        type: "line",
        source: "edges",
        "source-layer": "edges",
        layout: {"line-cap": "round", "line-join": "round"},
        paint: {"line-color": "#3b6fd8", "line-width": lineWidth(1)},
    });
    map.addLayer({
        id: "route-line",
        type: "line",
        source: "route-line",
        maxzoom: ROUTE_DETAIL_MIN_ZOOM,
        paint: {"line-color": "#d7263d", "line-width": 3, "line-dasharray": [2, 1]},
    });
    map.addLayer({
        id: "route",
        type: "line",
        source: "edges",
        "source-layer": "edges",
        filter: ["in", ["get", "eid"], ["literal", []]],
        layout: {"line-cap": "round", "line-join": "round"},
        paint: {"line-color": "#d7263d", "line-width": lineWidth(2.5)},
    });
    map.addLayer({
        id: "edge-hover",
        type: "line",
        source: "edges",
        "source-layer": "edges",
        filter: ["==", ["get", "eid"], -1],
        layout: {"line-cap": "round"},
        paint: {"line-color": "#f29e1f", "line-width": lineWidth(3)},
    });
    map.addLayer({
        id: "nodes",
        type: "circle",
        source: "nodes",
        "source-layer": "nodes",
        minzoom: NODES_MIN_ZOOM,
        layout: {visibility: "none"},
        paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], NODES_MIN_ZOOM, 1.5, 18, 5],
            "circle-color": "#1d2330",
        },
    });
}

function setUpHover(map, graph) {
    // nodes take precedence over the edges they lie on
    map.on("mousemove", (event) => {
        const layers = map.getLayoutProperty("nodes", "visibility") === "visible" ? ["nodes", "edges"] : ["edges"];
        const [feature] = map.queryRenderedFeatures(event.point, {layers});
        if (!feature) {
            map.setFilter("edge-hover", ["==", ["get", "eid"], -1]);
            hoverElement.textContent = "-";
            return;
        }
        if (feature.layer.id === "nodes") {
            const node = feature.properties.id;
            map.setFilter("edge-hover", ["==", ["get", "eid"], -1]);
            renderList(hoverElement, [["node", node], ["db_id", graph.dbIds[node]]]);
            return;
        }
        const edgeId = feature.properties.eid;
        const edge = graph.edge(edgeId);
        map.setFilter("edge-hover", ["==", ["get", "eid"], edgeId]);
        renderList(hoverElement, [
            ["edge (eid)", edgeId],
            ["u → v", `${edge.u} → ${edge.v}`],
            ["db_id_from", edge.dbIdFrom],
            ["db_id_to", edge.dbIdTo],
            ["length", formatLength(edge.length)],
        ]);
    });
}

function setUpNodesToggle(map) {
    const button = document.getElementById("toggle-nodes");
    button.addEventListener("click", () => {
        const visible = map.getLayoutProperty("nodes", "visibility") !== "visible";
        map.setLayoutProperty("nodes", "visibility", visible ? "visible" : "none");
        button.setAttribute("aria-pressed", String(visible));
        button.textContent = visible ? "Hide nodes" : "Show nodes";
        if (visible && map.getZoom() < NODES_MIN_ZOOM) {
            renderMessage(hoverElement, "Zoom in to see the nodes.");
        }
    });
}

class RoutePlanner {
    constructor(map, graphPromise) {
        this.map = map;
        this.graphPromise = graphPromise;
        this.markers = {start: null, target: null};
        this.nodes = {start: null, target: null};
        this.snapDistances = {start: null, target: null};
    }

    async handleClick(lngLat) {
        if (this.markers.start && this.markers.target) {
            this.clear();
        }
        await this.place(this.markers.start ? "target" : "start", lngLat);
    }

    async place(end, lngLat) {
        const graph = await this.graphPromise;
        const {node, distance} = graph.nearestNode(lngLat.lng, lngLat.lat);
        this.nodes[end] = node;
        this.snapDistances[end] = distance;
        if (this.markers[end]) {
            this.markers[end].setLngLat(graph.nodeCoordinates(node));
        } else {
            const marker = new Marker({color: end === "start" ? "#2e9d4f" : "#d7263d", draggable: true});
            marker.setLngLat(graph.nodeCoordinates(node)).addTo(this.map);
            marker.on("dragend", () => this.place(end, marker.getLngLat()));
            this.markers[end] = marker;
        }
        this.route(graph);
    }

    route(graph) {
        if (this.nodes.start === null || this.nodes.target === null) {
            renderMessage(routeElement, `Start: node ${this.nodes.start} (snapped ${formatLength(this.snapDistances.start)}). Click the target.`);
            return;
        }
        const startTime = performance.now();
        const path = graph.shortestPath(this.nodes.start, this.nodes.target);
        const duration = performance.now() - startTime;
        if (path === null) {
            this.showPath([], []);
            renderMessage(routeElement, `No path from node ${this.nodes.start} to node ${this.nodes.target}.`, true);
            return;
        }
        this.showPath(path.edgeIds, path.nodes.map((node) => graph.nodeCoordinates(node)));
        routeElement.classList.remove("error");
        renderList(routeElement, [
            ["length", formatLength(path.length)],
            ["edges", path.edgeIds.length],
            ["start node", `${this.nodes.start} (snapped ${formatLength(this.snapDistances.start)})`],
            ["target node", `${this.nodes.target} (snapped ${formatLength(this.snapDistances.target)})`],
            ["search", `${numberFormat.format(duration)} ms, ${path.settledCount} nodes settled`],
        ]);
    }

    showPath(edgeIds, coordinates) {
        this.map.setFilter("route", ["in", ["get", "eid"], ["literal", edgeIds]]);
        const features = coordinates.length > 1
            ? [{type: "Feature", properties: {}, geometry: {type: "LineString", coordinates}}]
            : [];
        this.map.getSource("route-line").setData({type: "FeatureCollection", features});
    }

    clear() {
        for (const end of ["start", "target"]) {
            this.markers[end]?.remove();
            this.markers[end] = null;
            this.nodes[end] = null;
            this.snapDistances[end] = null;
        }
        this.showPath([], []);
        renderMessage(routeElement, "No route.");
    }
}

async function main() {
    const response = await fetch("build.json", {cache: "no-store"});
    if (!response.ok) {
        throw new Error(`Failed to load build.json: ${response.status}`);
    }
    const build = await response.json();
    document.title = build.title;
    document.getElementById("title").textContent = build.title;
    document.getElementById("stats").textContent =
        `${build.node_count.toLocaleString("en")} nodes, ${build.edge_count.toLocaleString("en")} edges, build ${build.build_id}`;

    renderMessage(routeElement, "Loading the routing graph…");
    const graphPromise = loadGraph(build);
    graphPromise.then(
        () => renderMessage(routeElement, "No route."),
        (error) => renderMessage(routeElement, error.message, true),
    );

    const protocol = new Protocol();
    addProtocol("pmtiles", protocol.tile);

    const [minLon, minLat, maxLon, maxLat] = build.bounds;
    const map = new MapLibreMap({
        container: "map",
        style: BASEMAP_STYLE,
        bounds: [[minLon, minLat], [maxLon, maxLat]],
        fitBoundsOptions: {padding: 20},
        maxZoom: build.max_zoom + 4,
    });
    map.addControl(new NavigationControl(), "top-right");
    map.addControl(new ScaleControl(), "bottom-right");

    const planner = new RoutePlanner(map, graphPromise);
    map.on("load", () => {
        addNetworkLayers(map, build);
        graphPromise.then((graph) => setUpHover(map, graph));
        setUpNodesToggle(map);
        map.on("click", (event) => planner.handleClick(event.lngLat));
        document.getElementById("clear-route").addEventListener("click", () => planner.clear());
    });
}

main().catch((error) => renderMessage(routeElement, error.message, true));
