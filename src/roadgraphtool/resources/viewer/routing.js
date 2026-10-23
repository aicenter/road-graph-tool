// Shortest path search over the graph exported by roadgraphtool.viewer.write_graph. No DOM dependencies, so it can be
// imported from Node for verification.

const EARTH_RADIUS_M = 6371008.8;

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
        let offset = 0;
        const take = (ArrayType, length) => {
            const array = new ArrayType(buffer, offset, length);
            offset += length * ArrayType.BYTES_PER_ELEMENT;
            return array;
        };
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

    /** Returns the id of the node closest to the given coordinates and its distance in meters. */
    nearestNode(lon, lat) {
        const cosLat = Math.cos(lat * Math.PI / 180);
        let best = -1;
        let bestDistance = Infinity;
        for (let node = 0; node < this.nodeCount; node++) {
            const dx = (this.coords[2 * node] - lon) * cosLat;
            const dy = this.coords[2 * node + 1] - lat;
            const distance = dx * dx + dy * dy;
            if (distance < bestDistance) {
                bestDistance = distance;
                best = node;
            }
        }
        return {node: best, distance: Math.sqrt(bestDistance) * Math.PI / 180 * EARTH_RADIUS_M};
    }

    /**
     * Dijkstra's algorithm from source to target with the edge lengths as weights.
     * @returns {{nodes: number[], edgeIds: number[], length: number, settledCount: number} | null} null if the target
     * is not reachable
     */
    shortestPath(source, target) {
        const distances = new Float64Array(this.nodeCount).fill(Infinity);
        const previousEdge = new Int32Array(this.nodeCount).fill(-1);
        const settled = new Uint8Array(this.nodeCount);
        const heap = new MinHeap();
        distances[source] = 0;
        heap.push(source, 0);
        let settledCount = 0;

        while (heap.size > 0) {
            const node = heap.pop();
            if (settled[node]) {
                continue;
            }
            settled[node] = 1;
            settledCount++;
            if (node === target) {
                break;
            }
            for (let edge = this.offsets[node]; edge < this.offsets[node + 1]; edge++) {
                const next = this.targets[edge];
                const distance = distances[node] + this.lengths[edge];
                if (distance < distances[next]) {
                    distances[next] = distance;
                    previousEdge[next] = edge;
                    heap.push(next, distance);
                }
            }
        }

        if (!settled[target]) {
            return null;
        }
        const nodes = [target];
        const edgeIds = [];
        for (let node = target; node !== source;) {
            const edge = previousEdge[node];
            edgeIds.push(this.edgeIds[edge]);
            node = this.edgeSource(edge);
            nodes.push(node);
        }
        nodes.reverse();
        edgeIds.reverse();
        return {nodes, edgeIds, length: distances[target], settledCount};
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

    nodeCoordinates(node) {
        return [this.coords[2 * node], this.coords[2 * node + 1]];
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
