<!--
  The paper map of one category, drawn with Sigma.js.

  Every point is a paper at its UMAP position (a fixed projection of the
  SPECTER2 embedding of title and abstract), so papers on similar topics sit
  close together. Point size follows the citation count, colour the subject of
  the paper's primary category, which makes cross listed papers visible.

  Highlighting (search results, an author's papers) dims everything else and
  adds papers that are not on the map yet at their own position. Selecting a
  paper marks it and draws its citation edges to papers on the map.
-->
<script lang="ts">
    import Graph from "graphology";
    import Sigma from "sigma";
    import HoverCard from "$lib/components/HoverCard.svelte";
    import ZoomControls from "$lib/components/ZoomControls.svelte";
    import { CATEGORY_COLORS, categoryColor, subjectName, subjectOf } from "$lib/categories";
    import { citationCount, primaryCategory, truncate } from "$lib/paper";
    import { onThemeChange, token } from "$lib/theme";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        papers: Paper[];
        /** Papers to emphasise, everything else is dimmed. null = no highlight. */
        highlight: Paper[] | null;
        selected: Paper | null;
        onselect: (paper: Paper) => void;
    }

    let { papers, highlight, selected, onselect }: Props = $props();

    let container = $state<HTMLDivElement>();
    let width = $state(0);
    let hovered = $state<{ paper: Paper; x: number; y: number } | null>(null);
    let ring = $state<{ x: number; y: number; size: number } | null>(null);
    let themeVersion = $state(0);

    const byId = $derived(new Map(papers.map((p) => [p.entry_id, p])));
    const maxCitations = $derived(Math.max(1, ...papers.map(citationCount)));

    // subjects on this map, for the legend
    const legend = $derived.by(() => {
        const counts = new Map<string, number>();
        for (const p of papers) {
            const id = subjectOf(primaryCategory(p.categories)) || "other";
            counts.set(id, (counts.get(id) ?? 0) + 1);
        }
        return [...counts.entries()]
            .sort((a, b) => b[1] - a[1])
            .map(([id, count]) => ({
                id,
                name: id === "other" ? "Other" : subjectName(id),
                color: CATEGORY_COLORS[id] ?? token("--text-3", "#888"),
                count,
            }));
    });

    /**
     * Bounding box of the bulk of the papers: the initial view ignores a few
     * far away points, which would otherwise squeeze the map into a corner.
     */
    function robustBBox(list: Paper[]): { x: [number, number]; y: [number, number] } | null {
        if (list.length < 10) return null;
        const range = (values: number[]): [number, number] => {
            const sorted = [...values].sort((a, b) => a - b);
            const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
            const iqr = q(0.75) - q(0.25) || 1;
            const lo = Math.max(sorted[0], q(0.25) - 2 * iqr);
            const hi = Math.min(sorted[sorted.length - 1], q(0.75) + 2 * iqr);
            const pad = (hi - lo) * 0.05 || 1;
            return [lo - pad, hi + pad];
        };
        return { x: range(list.map((p) => p.x)), y: range(list.map((p) => p.y)) };
    }

    function nodeSize(p: Paper): number {
        return 2.2 + 5 * (Math.log1p(citationCount(p)) / Math.log1p(maxCitations));
    }

    function nodeAttributes(p: Paper) {
        return {
            x: p.x,
            y: p.y,
            size: nodeSize(p),
            color: categoryColor(p.categories),
            label: truncate(p.title, 70),
            zIndex: 1,
        };
    }

    $effect(() => {
        const stop = onThemeChange(() => themeVersion++);
        return stop;
    });

    // the renderer and the graph are rebuilt when the papers or the theme change
    let renderer: Sigma | null = null;
    let graph: Graph | null = null;
    let highlightSet: Set<string> | null = null;
    let selectedId: string | null = null;
    let neighbours = new Set<string>();

    $effect(() => {
        const list = papers;
        void themeVersion;
        const el = container;
        if (!el) return;

        const g = new Graph({ type: "directed" });
        const known = new Map<string, Paper>();
        for (const p of list) {
            if (g.hasNode(p.entry_id)) continue;
            g.addNode(p.entry_id, nodeAttributes(p));
            known.set(p.entry_id, p);
        }
        const dim = token("--map-dim", "rgba(0,0,0,0.1)");
        const labelColor = token("--map-label", "#1c1c1c");

        const r = new Sigma(g, el, {
            renderEdgeLabels: false,
            labelFont: "IBM Plex Sans, system-ui, sans-serif",
            labelSize: 11,
            labelWeight: "500",
            labelColor: { color: labelColor },
            labelRenderedSizeThreshold: 5.5,
            labelDensity: 0.3,
            labelGridCellSize: 150,
            defaultEdgeType: "arrow",
            zIndex: true,
            stagePadding: 48,
            minCameraRatio: 0.02,
            maxCameraRatio: 6,
            nodeReducer: (node, attrs) => {
                const out = { ...attrs };
                if (node === selectedId) {
                    out.size = attrs.size + 2;
                    out.zIndex = 3;
                    out.forceLabel = true;
                } else if (neighbours.has(node)) {
                    out.zIndex = 2;
                } else if (highlightSet) {
                    if (highlightSet.has(node)) {
                        out.size = Math.max(attrs.size, 3.5);
                        out.zIndex = 2;
                    } else {
                        out.color = dim;
                        out.label = "";
                        out.zIndex = 0;
                    }
                }
                return out;
            },
        });

        r.setCustomBBox(robustBBox(list));

        r.on("enterNode", ({ node, event }) => {
            const paper = known.get(node);
            if (paper) hovered = { paper, x: event.x, y: event.y };
            el.style.cursor = "pointer";
        });
        r.on("moveBody", ({ event }) => {
            if (hovered) hovered = { ...hovered, x: event.x, y: event.y };
        });
        r.on("leaveNode", () => {
            hovered = null;
            el.style.cursor = "";
        });
        r.on("clickNode", ({ node }) => {
            const paper = known.get(node);
            if (paper) onselect(paper);
        });
        r.getCamera().on("updated", updateRing);
        r.on("afterRender", updateRing);

        renderer = r;
        graph = g;
        injected = known;
        applyHighlight();
        applySelection();

        return () => {
            r.kill();
            renderer = null;
            graph = null;
            hovered = null;
            ring = null;
        };
    });

    // papers added for a highlight (not part of the category map)
    let injected = new Map<string, Paper>();
    let injectedIds: string[] = [];

    function applyHighlight() {
        if (!graph || !renderer) return;
        for (const id of injectedIds) if (graph.hasNode(id) && id !== selectedId) graph.dropNode(id);
        injectedIds = [];
        const list = highlight;
        if (!list) {
            highlightSet = null;
        } else {
            highlightSet = new Set(list.map((p) => p.entry_id));
            for (const p of list) {
                if (graph.hasNode(p.entry_id) || (p.x === 0 && p.y === 0)) continue;
                graph.addNode(p.entry_id, nodeAttributes(p));
                injected.set(p.entry_id, p);
                injectedIds.push(p.entry_id);
            }
        }
        renderer.refresh();
    }

    function applySelection() {
        if (!graph || !renderer) return;
        graph.clearEdges();
        neighbours = new Set();
        const paper = selected;
        selectedId = paper?.entry_id ?? null;
        if (paper) {
            // the map's own copy carries the citation lists, a search result does not
            const full = byId.get(paper.entry_id) ?? paper;
            if (!graph.hasNode(full.entry_id) && !(full.x === 0 && full.y === 0)) {
                graph.addNode(full.entry_id, nodeAttributes(full));
                injected.set(full.entry_id, full);
                injectedIds.push(full.entry_id);
            }
            if (graph.hasNode(full.entry_id)) {
                const edge = { type: "arrow", size: 1.2, color: token("--map-edge", "rgba(0,0,0,0.3)") };
                for (const id of full.references) {
                    if (graph.hasNode(id)) {
                        graph.addEdge(full.entry_id, id, edge);
                        neighbours.add(id);
                    }
                }
                for (const id of full.citations) {
                    if (graph.hasNode(id) && !graph.hasEdge(id, full.entry_id)) {
                        graph.addEdge(id, full.entry_id, edge);
                        neighbours.add(id);
                    }
                }
            }
        }
        renderer.refresh();
        updateRing();
    }

    function updateRing() {
        if (!renderer || !graph || !selectedId || !graph.hasNode(selectedId)) {
            ring = null;
            return;
        }
        const data = renderer.getNodeDisplayData(selectedId);
        if (!data) {
            ring = null;
            return;
        }
        const pos = renderer.framedGraphToViewport(data);
        ring = { x: pos.x, y: pos.y, size: renderer.scaleSize(data.size) * 2 + 8 };
    }

    $effect(() => {
        void highlight;
        applyHighlight();
    });
    $effect(() => {
        void selected;
        void byId;
        applySelection();
    });

    const camera = () => renderer?.getCamera();
</script>

<div class="map" bind:clientWidth={width}>
    <div class="canvas" bind:this={container}></div>

    {#if ring}
        <div
            class="ring"
            aria-hidden="true"
            style:left="{ring.x}px"
            style:top="{ring.y}px"
            style:width="{ring.size}px"
            style:height="{ring.size}px"
        ></div>
    {/if}

    {#if hovered}
        <HoverCard paper={hovered.paper} x={hovered.x} y={hovered.y} {width} />
    {/if}

    <div class="legend">
        {#each legend as item (item.id)}
            <span><i style:background={item.color}></i>{item.name} <b>{item.count.toLocaleString("en")}</b></span>
        {/each}
        <span class="hint">size: citations · position: UMAP of the SPECTER2 embedding</span>
    </div>

    <ZoomControls
        onzoomin={() => camera()?.animatedZoom({ duration: 200 })}
        onzoomout={() => camera()?.animatedUnzoom({ duration: 200 })}
        onreset={() => camera()?.animatedReset({ duration: 300 })}
    />
</div>

<style>
    .map {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: var(--bg);
    }
    .canvas {
        position: absolute;
        inset: 0;
    }
    .ring {
        position: absolute;
        transform: translate(-50%, -50%);
        border: 2px solid var(--text);
        border-radius: 50%;
        pointer-events: none;
    }

    .legend {
        position: absolute;
        left: 12px;
        bottom: 12px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px 14px;
        max-width: calc(100% - 70px);
        padding: 6px 10px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        color: var(--text-2);
        font-size: var(--text-xs);
        pointer-events: none;
    }
    .legend span {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .legend i {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    .legend b {
        color: var(--text-3);
        font-family: var(--font-mono);
        font-weight: 400;
    }
    .legend .hint {
        color: var(--text-3);
    }
</style>
