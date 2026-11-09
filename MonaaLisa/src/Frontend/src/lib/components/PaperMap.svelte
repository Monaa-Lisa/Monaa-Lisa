<!--
  The paper map of one category, drawn with Sigma.js.

  Every point is a paper at its UMAP position (a fixed projection of the
  SPECTER2 embedding of title and abstract), so papers on similar topics sit
  close together. Point size follows the citation count, colour either the
  primary category of the paper (the three most common ones on this map, the
  rest is grey) or its year of publication (`colorBy`).

  Titles are HTML elements placed by lib/labels.ts: the most cited papers
  first, as many as fit without overlap, more when zooming in.

  Highlighting (search results, an author's papers) dims everything else and
  adds papers that are not on the map yet at their own position. Selecting a
  paper marks it and draws its citation edges to papers on the map.
-->
<script module lang="ts">
    export type ColorBy = "category" | "year";
</script>

<script lang="ts">
    import { untrack } from "svelte";
    import Graph from "graphology";
    import Sigma from "sigma";
    import HoverCard from "$lib/components/HoverCard.svelte";
    import ZoomControls from "$lib/components/ZoomControls.svelte";
    import { DEFAULT_CATEGORY_COLOR, subcategoryName } from "$lib/categories";
    import { createLabelPlacer, overlayBoxes, type PlacedLabel } from "$lib/labels";
    import { citationCount, primaryCategory, publishedYear, truncate } from "$lib/paper";
    import { onThemeChange, resolveColor, token, withAlpha } from "$lib/theme";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        papers: Paper[];
        /** Papers to emphasise, everything else is dimmed. null = no highlight. */
        highlight: Paper[] | null;
        selected: Paper | null;
        colorBy: ColorBy;
        onselect: (paper: Paper) => void;
    }

    let { papers, highlight, selected, colorBy, onselect }: Props = $props();

    let container = $state<HTMLDivElement>();
    let width = $state(0);
    let hovered = $state<{ paper: Paper; x: number; y: number } | null>(null);
    let ring = $state<{ x: number; y: number; size: number } | null>(null);
    let labels = $state<PlacedLabel[]>([]);
    let themeVersion = $state(0);

    const byId = $derived(new Map(papers.map((p) => [p.entry_id, p])));
    const maxCitations = $derived(Math.max(1, ...papers.map(citationCount)));

    interface Scheme {
        /** Colour of a paper as a CSS value */
        colorOf: (p: Paper) => string;
        legend: { id: string; name: string; detail?: string; color: string; count: number }[];
    }

    /** At most this many categories get a colour of their own, more can not be told apart on a scatter */
    const CATEGORY_SLOTS = 3;
    const YEAR_STEPS = 5;

    function categoryScheme(list: Paper[]): Scheme {
        const counts = new Map<string, number>();
        for (const p of list) {
            const id = primaryCategory(p.categories);
            counts.set(id, (counts.get(id) ?? 0) + 1);
        }
        const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1]);
        const top = ranked.slice(0, CATEGORY_SLOTS);
        const slot = new Map(top.map(([id], i) => [id, `var(--series-${i + 1})`]));
        const legend = top.map(([id, count]) => ({
            id,
            name: subcategoryName(id),
            detail: id,
            color: slot.get(id)!,
            count,
        }));
        const rest = ranked.slice(CATEGORY_SLOTS);
        if (rest.length) {
            legend.push({
                id: "other",
                name: `${rest.length} other ${rest.length === 1 ? "category" : "categories"}`,
                detail: "",
                color: DEFAULT_CATEGORY_COLOR,
                count: rest.reduce((sum, [, n]) => sum + n, 0),
            });
        }
        return { colorOf: (p) => slot.get(primaryCategory(p.categories)) ?? DEFAULT_CATEGORY_COLOR, legend };
    }

    /** Years in up to five groups of about the same number of papers, old (light) to recent (dark) */
    function yearScheme(list: Paper[]): Scheme {
        const years = list
            .map((p) => Number(publishedYear(p.published)))
            .filter(Boolean)
            .sort((a, b) => a - b);
        if (!years.length) return { colorOf: () => DEFAULT_CATEGORY_COLOR, legend: [] };
        // last year of every group
        const ends: number[] = [];
        for (let i = 1; i <= YEAR_STEPS; i++) {
            const end = years[Math.min(years.length - 1, Math.ceil((i / YEAR_STEPS) * years.length) - 1)];
            if (ends.at(-1) !== end) ends.push(end);
        }
        // with fewer groups the steps are spread over the whole ramp
        const step = (i: number) =>
            ends.length === 1 ? 3 : 1 + Math.round((i * (YEAR_STEPS - 1)) / (ends.length - 1));
        const group = (year: number) => {
            const i = ends.findIndex((end) => year <= end);
            return i < 0 ? ends.length - 1 : i;
        };
        const counts = ends.map(() => 0);
        for (const year of years) counts[group(year)]++;
        const legend = ends.map((end, i) => {
            const start = i === 0 ? years[0] : ends[i - 1] + 1;
            return {
                id: String(end),
                name: start === end ? String(end) : `${start}–${String(end).slice(2)}`,
                color: `var(--seq-${step(i)})`,
                count: counts[i],
            };
        });
        return {
            colorOf: (p) => {
                const year = Number(publishedYear(p.published));
                return year ? `var(--seq-${step(group(year))})` : DEFAULT_CATEGORY_COLOR;
            },
            legend,
        };
    }

    const scheme = $derived(colorBy === "year" ? yearScheme(papers) : categoryScheme(papers));

    /** Slightly transparent, so points lying on each other show how dense a spot is */
    const nodeColor = (p: Paper, s: Scheme) => withAlpha(resolveColor(s.colorOf(p)), 0.8);

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
        return 1.8 + 4.6 * (Math.log1p(citationCount(p)) / Math.log1p(maxCitations));
    }

    function nodeAttributes(p: Paper) {
        return { x: p.x, y: p.y, size: nodeSize(p), color: nodeColor(p, untrack(() => scheme)), zIndex: 1 };
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
    /** Every paper with a node, including the ones added for a highlight */
    let nodes = new Map<string, Paper>();
    /** Nodes added for a highlight (not part of the category map) */
    let injectedIds: string[] = [];
    let relabel = () => {};

    /** Papers that may carry a title, most important first */
    function candidates() {
        const list = [...nodes.values()]
            .filter((p) => graph?.hasNode(p.entry_id) && (!highlightSet || highlightSet.has(p.entry_id)))
            .sort((a, b) => citationCount(b) - citationCount(a));
        const i = list.findIndex((p) => p.entry_id === selectedId);
        if (i > 0) list.unshift(...list.splice(i, 1));
        return list.map((p) => ({ id: p.entry_id, label: truncate(p.title, 90) }));
    }

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

        const r = new Sigma(g, el, {
            // titles are HTML elements placed by lib/labels.ts
            renderLabels: false,
            renderEdgeLabels: false,
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
                } else if (neighbours.has(node)) {
                    out.zIndex = 2;
                } else if (highlightSet) {
                    if (highlightSet.has(node)) {
                        out.size = Math.max(attrs.size, 3.5);
                        out.zIndex = 2;
                    } else {
                        out.color = dim;
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

        // titles are placed after a render and again whenever the camera moved
        const placer = createLabelPlacer(r, 30, () => overlayBoxes(el));
        let needsLabels = true;
        r.getCamera().on("updated", () => (needsLabels = true));
        r.on("afterRender", () => {
            if (!needsLabels) return;
            needsLabels = false;
            labels = placer.place(candidates());
        });
        relabel = () => {
            needsLabels = true;
            r.refresh();
        };

        renderer = r;
        graph = g;
        nodes = known;
        applyHighlight();
        applySelection();

        return () => {
            r.kill();
            renderer = null;
            graph = null;
            hovered = null;
            ring = null;
            labels = [];
            relabel = () => {};
        };
    });

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
                nodes.set(p.entry_id, p);
                injectedIds.push(p.entry_id);
            }
        }
        relabel();
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
                nodes.set(full.entry_id, full);
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
        relabel();
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
    // switching the colouring repaints the points and keeps the view
    $effect(() => {
        const s = scheme;
        if (!graph) return;
        for (const [id, p] of nodes) if (graph.hasNode(id)) graph.setNodeAttribute(id, "color", nodeColor(p, s));
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

    {#each labels as item (item.id)}
        <span
            class="node-label"
            class:primary={item.id === selected?.entry_id}
            style:left="{item.x}px"
            style:top="{item.y}px"
            style:width="{item.width}px">{item.label}</span
        >
    {/each}

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
        {#each scheme.legend as item (item.id)}
            <span>
                <i style:background={item.color}></i>{item.name}
                {#if item.detail}<em>{item.detail}</em>{/if}
                <b>{item.count.toLocaleString("en")}</b>
            </span>
        {/each}
        <span class="hint">close points = similar content · size = citations · zoom for more titles</span>
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
        font-variant-numeric: tabular-nums;
        font-weight: 400;
    }
    .legend em {
        color: var(--text-3);
        font-style: normal;
    }
    .legend .hint {
        color: var(--text-3);
    }
</style>
