// Snapping to the edges and shortest path search over the files exported by roadgraphtool.viewer (graph.bin and
// shapes.bin). No DOM dependencies, so it can be imported from Node for verification.

const EARTH_RADIUS_M = 6371008.8;
const METERS_PER_DEGREE = Math.PI / 180 * EARTH_RADIUS_M;

function arrayReader(buffer) {
    let offset = 0;
    return (ArrayType, length) => {
        const array = new ArrayType(buffer, offset, length);
        offset += length * ArrayType.BYTES_PER_ELEMENT;
        return array;
    };
}

/**
 * A point on an edge feature: the edge in the direction of the shape (eid), its reverse edge (eid2, -1 for one-way
 * edges), and the position of the point as a fraction of the shape length, measured from the start of eid.
 * @typedef {{eid: number, eid2: number, fraction: number}} EdgePoint
 */

/**
 * A part of an edge: the edge id and the start and end of the part as fractions of the edge, in the edge direction.
 * @typedef {{eid: number, from: number, to: number}} EdgeSegment
 */

export class Graph {
    /**
     * @param {ArrayBuffer} buffer content of graph.bin
     * @param {number} nodeCount
     * @param {number} edgeCount
     */
    constructor(buffer, nodeCount, edgeCount) {
        const expectedSize = 16 * nodeCount + 4 * (nodeCount + 1) + 12 * edgeCount;
        if (buffer.byteLength !== expectedSize) {
            throw new Error(`graph.bin has ${buffer.byteLength} bytes, expected ${expectedSize}`);
        }
        const take = arrayReader(buffer);
        this.nodeCount = nodeCount;
        this.edgeCount = edgeCount;
        this.dbIds = take(Float64Array, nodeCount);
        this.coords = take(Float32Array, 2 * nodeCount);
        this.offsets = take(Uint32Array, nodeCount + 1);
        this.targets = take(Uint32Array, edgeCount);
        this.lengths = take(Float32Array, edgeCount);
        this.edgeIds = take(Uint32Array, edgeCount);
        // CSR position of each edge id
        this.edgePositions = new Uint32Array(edgeCount);
        for (let edge = 0; edge < edgeCount; edge++) {
            this.edgePositions[this.edgeIds[edge]] = edge;
        }
    }

    /** Returns the attributes of the edge with the given id (the eid of the edge feature in the tiles). */
    edge(edgeId) {
        const position = this.edgePositions[edgeId];
        const u = this.edgeSource(position);
        const v = this.targets[position];
        return {u, v, dbIdFrom: this.dbIds[u], dbIdTo: this.dbIds[v], length: this.lengths[position]};
    }

    /**
     * Dijkstra's algorithm between two points on edges, with the edge lengths as weights. The path leaves the source
     * edge to one of its end nodes (to the start node only if the edge is two-way) and enters the target edge
     * from one of its end nodes, or goes directly along the edge if both points are on the same edge.
     * @param {EdgePoint} source
     * @param {EdgePoint} target
     * @returns {{segments: EdgeSegment[], length: number, settledCount: number} | null} the parts of the edges on the
     * path in the travel order, or null if the target is not reachable
     */
    shortestPath(source, target) {
        const starts = this.#exits(source);
        const ends = this.#entries(target);
        let best = Infinity;
        let bestEnd = null;
        let direct = null;
        if (source.eid === target.eid) {
            for (const option of this.#directOptions(source, target)) {
                if (option.length < best) {
                    best = option.length;
                    direct = option.segment;
                }
            }
        }

        const distances = new Float64Array(this.nodeCount).fill(Infinity);
        const previousEdge = new Int32Array(this.nodeCount).fill(-1);
        // index of the start through which the node was reached directly from the source, -1 otherwise
        const startOf = new Int8Array(this.nodeCount).fill(-1);
        const settled = new Uint8Array(this.nodeCount);
        const heap = new MinHeap();
        starts.forEach((start, index) => {
            if (start.cost < distances[start.node]) {
                distances[start.node] = start.cost;
                startOf[start.node] = index;
                heap.push(start.node, start.cost);
            }
        });

        let settledCount = 0;
        while (heap.size > 0) {
            const node = heap.pop();
            if (settled[node]) {
                continue;
            }
            const distance = distances[node];
            // the remaining nodes are not closer, so the path cannot be improved
            if (distance >= best) {
                break;
            }
            settled[node] = 1;
            settledCount++;
            for (const end of ends) {
                if (end.node === node && distance + end.cost < best) {
                    best = distance + end.cost;
                    bestEnd = end;
                    direct = null;
                }
            }
            for (let edge = this.offsets[node]; edge < this.offsets[node + 1]; edge++) {
                const next = this.targets[edge];
                const nextDistance = distance + this.lengths[edge];
                if (nextDistance < distances[next]) {
                    distances[next] = nextDistance;
                    previousEdge[next] = edge;
                    startOf[next] = -1;
                    heap.push(next, nextDistance);
                }
            }
        }

        if (direct !== null) {
            return {segments: [direct], length: best, settledCount};
        }
        if (bestEnd === null) {
            return null;
        }
        const segments = [bestEnd.segment];
        let node = bestEnd.node;
        while (previousEdge[node] !== -1) {
            const edge = previousEdge[node];
            segments.push({eid: this.edgeIds[edge], from: 0, to: 1});
            node = this.edgeSource(edge);
        }
        segments.push(starts[startOf[node]].segment);
        segments.reverse();
        return {segments, length: best, settledCount};
    }

    /** The ways from a point to the end nodes of its edge: the target node and the cost of getting there. */
    #exits(point) {
        const edge = this.edge(point.eid);
        const exits = [{
            node: edge.v,
            cost: (1 - point.fraction) * edge.length,
            segment: {eid: point.eid, from: point.fraction, to: 1},
        }];
        if (point.eid2 >= 0) {
            const reverse = this.edge(point.eid2);
            exits.push({
                node: reverse.v,
                cost: point.fraction * reverse.length,
                segment: {eid: point.eid2, from: 1 - point.fraction, to: 1},
            });
        }
        return exits;
    }

    /** The ways from the end nodes of an edge to a point on it: the start node and the cost from there. */
    #entries(point) {
        const edge = this.edge(point.eid);
        const entries = [{
            node: edge.u,
            cost: point.fraction * edge.length,
            segment: {eid: point.eid, from: 0, to: point.fraction},
        }];
        if (point.eid2 >= 0) {
            const reverse = this.edge(point.eid2);
            entries.push({
                node: reverse.u,
                cost: (1 - point.fraction) * reverse.length,
                segment: {eid: point.eid2, from: 0, to: 1 - point.fraction},
            });
        }
        return entries;
    }

    /** The ways between two points on the same edge feature along the edge itself. */
    #directOptions(source, target) {
        const options = [];
        if (source.fraction <= target.fraction) {
            options.push({
                length: (target.fraction - source.fraction) * this.edge(source.eid).length,
                segment: {eid: source.eid, from: source.fraction, to: target.fraction},
            });
        }
        if (source.eid2 >= 0 && source.fraction >= target.fraction) {
            options.push({
                length: (source.fraction - target.fraction) * this.edge(source.eid2).length,
                segment: {eid: source.eid2, from: 1 - source.fraction, to: 1 - target.fraction},
            });
        }
        return options;
    }

    /** Source node of the edge at the given CSR position (binary search over the offsets). */
    edgeSource(edge) {
        let low = 0;
        let high = this.nodeCount - 1;
        while (low < high) {
            const middle = (low + high + 1) >>> 1;
            if (this.offsets[middle] <= edge) {
                low = middle;
            } else {
                high = middle - 1;
            }
        }
        return low;
    }
}

/** The shapes of the edge features with an R-tree for finding the nearest point on an edge. */
export class EdgeShapes {
    /**
     * @param {ArrayBuffer} buffer content of shapes.bin
     * @param {number} shapeCount
     * @param {number} vertexCount
     * @param {number} edgeCount
     * @param {typeof import("flatbush").default} Flatbush the R-tree class of the Flatbush library
     */
    constructor(buffer, shapeCount, vertexCount, edgeCount, Flatbush) {
        const expectedSize = 12 * shapeCount + 4 + 8 * vertexCount;
        if (buffer.byteLength !== expectedSize) {
            throw new Error(`shapes.bin has ${buffer.byteLength} bytes, expected ${expectedSize}`);
        }
        const take = arrayReader(buffer);
        this.shapeCount = shapeCount;
        this.eids = take(Int32Array, shapeCount);
        this.reverseEids = take(Int32Array, shapeCount);
        this.offsets = take(Uint32Array, shapeCount + 1);
        this.coords = take(Float32Array, 2 * vertexCount);

        // shape of each edge and whether the edge goes against the shape direction
        this.shapeOfEdge = new Int32Array(edgeCount).fill(-1);
        this.edgeIsReverse = new Uint8Array(edgeCount);
        for (let shape = 0; shape < shapeCount; shape++) {
            this.shapeOfEdge[this.eids[shape]] = shape;
            if (this.reverseEids[shape] >= 0) {
                this.shapeOfEdge[this.reverseEids[shape]] = shape;
                this.edgeIsReverse[this.reverseEids[shape]] = 1;
            }
        }

        // the R-tree and the distances work in meters, in an equirectangular projection around the middle latitude
        let minLat = Infinity;
        let maxLat = -Infinity;
        for (let vertex = 0; vertex < vertexCount; vertex++) {
            minLat = Math.min(minLat, this.coords[2 * vertex + 1]);
            maxLat = Math.max(maxLat, this.coords[2 * vertex + 1]);
        }
        this.xScale = Math.cos((minLat + maxLat) / 2 * Math.PI / 180) * METERS_PER_DEGREE;
        this.yScale = METERS_PER_DEGREE;

        this.index = new Flatbush(shapeCount);
        for (let shape = 0; shape < shapeCount; shape++) {
            let minX = Infinity;
            let minY = Infinity;
            let maxX = -Infinity;
            let maxY = -Infinity;
            for (let vertex = this.offsets[shape]; vertex < this.offsets[shape + 1]; vertex++) {
                const x = this.coords[2 * vertex] * this.xScale;
                const y = this.coords[2 * vertex + 1] * this.yScale;
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x);
                maxY = Math.max(maxY, y);
            }
            this.index.add(minX, minY, maxX, maxY);
        }
        this.index.finish();
    }

    /**
     * Returns the point on an edge nearest to the given coordinates, its coordinates, and its distance in meters.
     * @returns {EdgePoint & {coordinates: number[], distance: number}}
     */
    nearestPoint(lon, lat) {
        const x = lon * this.xScale;
        const y = lat * this.yScale;
        // the nearest shape by the bounding box gives an upper bound for the exact distance
        let best = this.#nearestOnShape(this.index.neighbors(x, y, 1)[0], x, y);
        for (const shape of this.index.neighbors(x, y, Infinity, best.distance)) {
            const candidate = this.#nearestOnShape(shape, x, y);
            if (candidate.distance < best.distance) {
                best = candidate;
            }
        }
        return {
            eid: this.eids[best.shape],
            eid2: this.reverseEids[best.shape],
            fraction: best.fraction,
            coordinates: [best.x / this.xScale, best.y / this.yScale],
            distance: best.distance,
        };
    }

    /** Coordinates of the part of the edge between the given fractions of its length, in the edge direction. */
    edgeCoordinates(eid, from, to) {
        const shape = this.shapeOfEdge[eid];
        if (!this.edgeIsReverse[eid]) {
            return this.#shapeCoordinates(shape, from, to);
        }
        return this.#shapeCoordinates(shape, 1 - to, 1 - from).reverse();
    }

    #vertex(vertex) {
        return [this.coords[2 * vertex] * this.xScale, this.coords[2 * vertex + 1] * this.yScale];
    }

    #shapeLength(shape) {
        let length = 0;
        for (let vertex = this.offsets[shape] + 1; vertex < this.offsets[shape + 1]; vertex++) {
            const [x0, y0] = this.#vertex(vertex - 1);
            const [x1, y1] = this.#vertex(vertex);
            length += Math.hypot(x1 - x0, y1 - y0);
        }
        return length;
    }

    #nearestOnShape(shape, x, y) {
        const start = this.offsets[shape];
        const end = this.offsets[shape + 1];
        let [bestX, bestY] = this.#vertex(start);
        let bestDistance = Math.hypot(bestX - x, bestY - y);
        let bestAlong = 0;
        let along = 0;
        for (let vertex = start + 1; vertex < end; vertex++) {
            const [x0, y0] = this.#vertex(vertex - 1);
            const [x1, y1] = this.#vertex(vertex);
            const dx = x1 - x0;
            const dy = y1 - y0;
            const segmentLength = Math.hypot(dx, dy);
            const t = segmentLength > 0 ? Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / segmentLength ** 2)) : 0;
            const px = x0 + t * dx;
            const py = y0 + t * dy;
            const distance = Math.hypot(px - x, py - y);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestX = px;
                bestY = py;
                bestAlong = along + t * segmentLength;
            }
            along += segmentLength;
        }
        return {shape, x: bestX, y: bestY, distance: bestDistance, fraction: along > 0 ? bestAlong / along : 0};
    }

    /** Coordinates (lon, lat) of the part of the shape between the given fractions of its length (from <= to). */
    #shapeCoordinates(shape, from, to) {
        const total = this.#shapeLength(shape);
        const fromLength = from * total;
        const toLength = to * total;
        const toLonLat = ([x, y]) => [x / this.xScale, y / this.yScale];
        const start = this.offsets[shape];
        const end = this.offsets[shape + 1];
        if (end - start === 1 || total === 0) {
            return [toLonLat(this.#vertex(start))];
        }
        const coordinates = [];
        let along = 0;
        for (let vertex = start + 1; vertex < end; vertex++) {
            const [x0, y0] = this.#vertex(vertex - 1);
            const [x1, y1] = this.#vertex(vertex);
            const segmentLength = Math.hypot(x1 - x0, y1 - y0);
            // the last segment ends the shape even if the summed lengths differ by a rounding error
            const segmentEnd = vertex === end - 1 ? Infinity : along + segmentLength;
            const interpolate = (length) => {
                const t = segmentLength > 0 ? Math.min(1, (length - along) / segmentLength) : 0;
                return [x0 + t * (x1 - x0), y0 + t * (y1 - y0)];
            };
            if (coordinates.length === 0 && fromLength <= segmentEnd) {
                coordinates.push(toLonLat(interpolate(fromLength)));
            }
            if (coordinates.length > 0) {
                if (toLength <= segmentEnd) {
                    coordinates.push(toLonLat(interpolate(toLength)));
                    break;
                }
                coordinates.push(toLonLat([x1, y1]));
            }
            along += segmentLength;
        }
        return coordinates;
    }
}

/** Binary min-heap of (item, key) pairs, with duplicates allowed (lazy deletion in Dijkstra). */
class MinHeap {
    constructor() {
        this.items = [];
        this.keys = [];
    }

    get size() {
        return this.items.length;
    }

    push(item, key) {
        const items = this.items;
        const keys = this.keys;
        let index = items.length;
        items.push(item);
        keys.push(key);
        while (index > 0) {
            const parent = (index - 1) >> 1;
            if (keys[parent] <= key) {
                break;
            }
            items[index] = items[parent];
            keys[index] = keys[parent];
            index = parent;
        }
        items[index] = item;
        keys[index] = key;
    }

    pop() {
        const items = this.items;
        const keys = this.keys;
        const top = items[0];
        const lastItem = items.pop();
        const lastKey = keys.pop();
        const size = items.length;
        if (size > 0) {
            let index = 0;
            while (true) {
                let child = 2 * index + 1;
                if (child >= size) {
                    break;
                }
                if (child + 1 < size && keys[child + 1] < keys[child]) {
                    child++;
                }
                if (keys[child] >= lastKey) {
                    break;
                }
                items[index] = items[child];
                keys[index] = keys[child];
                index = child;
            }
            items[index] = lastItem;
            keys[index] = lastKey;
        }
        return top;
    }
}
