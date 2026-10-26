import {MapLibreMap, Marker, NavigationControl, ScaleControl, addProtocol} from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.12.0/dist/maplibre-gl.mjs";
import {Protocol} from "https://cdn.jsdelivr.net/npm/pmtiles@4.5.0/+esm";
import Flatbush from "https://cdn.jsdelivr.net/npm/flatbush@4.6.2/+esm";
import {EdgeShapes, Graph} from "./routing.js";

const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
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

async function fetchBinary(fileName, build) {
    const response = await fetch(dataUrl(fileName, build.build_id));
    if (!response.ok) {
        throw new Error(`Failed to load ${fileName}: ${response.status}`);
    }
    return response.arrayBuffer();
}

/** Loads the routing graph and the edge shapes. */
async function loadNetwork(build) {
    const [graphBuffer, shapesBuffer] = await Promise.all([fetchBinary("graph.bin", build), fetchBinary("shapes.bin", build)]);
    return {
        graph: new Graph(graphBuffer, build.node_count, build.edge_count),
        shapes: new EdgeShapes(shapesBuffer, build.shape_count, build.vertex_count, build.edge_count, Flatbush),
    };
}

function addNetworkLayers(map, build) {
    map.addSource("edges", {type: "vector", url: `pmtiles://${dataUrl("edges.pmtiles", build.build_id)}`});
    map.addSource("nodes", {type: "vector", url: `pmtiles://${dataUrl("nodes.pmtiles", build.build_id)}`});
    map.addSource("route", {type: "geojson", data: {type: "FeatureCollection", features: []}});

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
        id: "route",
        type: "line",
        source: "route",
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
        // a two-way edge is one feature with the ids of both directions (eid2 is -1 for one-way edges)
        const {eid, eid2} = feature.properties;
        const edge = graph.edge(eid);
        map.setFilter("edge-hover", ["==", ["get", "eid"], eid]);
        const entries = [
            ["edge (eid)", eid],
            ["u → v", `${edge.u} → ${edge.v}`],
            ["db_id_from", edge.dbIdFrom],
            ["db_id_to", edge.dbIdTo],
            ["length", formatLength(edge.length)],
        ];
        if (eid2 >= 0) {
            const reverse = graph.edge(eid2);
            entries.push(["reverse edge", `${eid2} (${formatLength(reverse.length)})`]);
        } else {
            entries.push(["reverse edge", "none (one-way)"]);
        }
        renderList(hoverElement, entries);
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

function describePoint(point) {
    return `edge ${point.eid} at ${numberFormat.format(point.fraction * 100)} % (snapped ${formatLength(point.distance)})`;
}

class RoutePlanner {
    constructor(map, networkPromise) {
        this.map = map;
        this.networkPromise = networkPromise;
        this.markers = {start: null, target: null};
        // the points on the edges nearest to the clicked points
        this.points = {start: null, target: null};
    }

    async handleClick(lngLat) {
        if (this.markers.start && this.markers.target) {
            this.clear();
        }
        await this.place(this.markers.start ? "target" : "start", lngLat);
    }

    async place(end, lngLat) {
        const network = await this.networkPromise;
        const point = network.shapes.nearestPoint(lngLat.lng, lngLat.lat);
        this.points[end] = point;
        if (this.markers[end]) {
            this.markers[end].setLngLat(point.coordinates);
        } else {
            const marker = new Marker({color: end === "start" ? "#2e9d4f" : "#d7263d", draggable: true});
            marker.setLngLat(point.coordinates).addTo(this.map);
            marker.on("dragend", () => this.place(end, marker.getLngLat()));
            this.markers[end] = marker;
        }
        this.route(network);
    }

    route({graph, shapes}) {
        const {start, target} = this.points;
        if (start === null || target === null) {
            renderMessage(routeElement, `Start: ${describePoint(start)}. Click the target.`);
            return;
        }
        const startTime = performance.now();
        const path = graph.shortestPath(start, target);
        const duration = performance.now() - startTime;
        if (path === null) {
            this.showPath([]);
            renderMessage(routeElement, `No path from edge ${start.eid} to edge ${target.eid}.`, true);
            return;
        }
        const coordinates = [];
        for (const segment of path.segments) {
            // consecutive segments share their end point
            const segmentCoordinates = shapes.edgeCoordinates(segment.eid, segment.from, segment.to);
            coordinates.push(...(coordinates.length > 0 ? segmentCoordinates.slice(1) : segmentCoordinates));
        }
        this.showPath(coordinates);
        routeElement.classList.remove("error");
        renderList(routeElement, [
            ["length", formatLength(path.length)],
            ["edges", `${path.segments.length} (first and last partially)`],
            ["start", describePoint(start)],
            ["target", describePoint(target)],
            ["search", `${numberFormat.format(duration)} ms, ${path.settledCount} nodes settled`],
        ]);
    }

    showPath(coordinates) {
        const features = coordinates.length > 1
            ? [{type: "Feature", properties: {}, geometry: {type: "LineString", coordinates}}]
            : [];
        this.map.getSource("route").setData({type: "FeatureCollection", features});
    }

    clear() {
        for (const end of ["start", "target"]) {
            this.markers[end]?.remove();
            this.markers[end] = null;
            this.points[end] = null;
        }
        this.showPath([]);
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
    const networkPromise = loadNetwork(build);
    networkPromise.then(
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

    const planner = new RoutePlanner(map, networkPromise);
    map.on("load", () => {
        addNetworkLayers(map, build);
        networkPromise.then(({graph}) => setUpHover(map, graph));
        setUpNodesToggle(map);
        map.on("click", (event) => planner.handleClick(event.lngLat));
        document.getElementById("clear-route").addEventListener("click", () => planner.clear());
    });
}

main().catch((error) => renderMessage(routeElement, error.message, true));
