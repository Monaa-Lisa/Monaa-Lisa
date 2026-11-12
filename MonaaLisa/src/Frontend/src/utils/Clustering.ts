import type Graph from 'graphology'
import louvain from 'graphology-communities-louvain'
import forceAtlas2 from 'graphology-layout-forceatlas2'

export function clusterWithLouvain(graph: Graph): Record<string, number> {
    return louvain(graph)
}

export function applyForceAtlas2(graph: Graph, options: { iterations?: number } = {}) {
    const params = { iterations: 100, ...options }; // Default to 100 iterations if not provided
    forceAtlas2.assign(graph, params);
}