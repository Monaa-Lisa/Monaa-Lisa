<!--
  The citation neighbourhood of one paper, drawn with Sigma.js. Two layouts:

  citations  a chart: x = year of publication, y = citations (log scale).
             The papers it cites are mostly to the left of the selected
             paper (older), the papers citing it to the right (newer), and
             the most cited work sits at the top. Only the most cited papers
             of each group are shown by default (nodeLimit). Every point is
             linked to the selected paper, so the links are not drawn; hover
             a point to see its link.
  related    the papers most similar to it (lib/neighbourhood.ts) at their map positions
             around the selected paper, i.e. its neighbourhood on the map.
             The papers of the open category map are drawn in grey behind
             them (`context`), so the neighbourhood has its surroundings.

  Nodes are coloured by subject like everywhere else, so citations from other
  fields stand out. Titles are HTML elements placed by lib/labels.ts.
-->
<script module lang="ts">
    export type NetworkMode = "citations" | "related";
</script>

<script lang="ts">
    import Graph from "graphology";
    import Sigma from "sigma";
    import HoverCard from "$lib/components/HoverCard.svelte";
    import Spinner from "$lib/components/ui/Spinner.svelte";
    import ZoomControls from "$lib/components/ZoomControls.svelte";
    import { categoryColor, subjectColor, subjectName, subjectOf } from "$lib/categories";
    import { createLabelPlacer, overlayBoxes, type PlacedLabel } from "$lib/labels";
    import { loadConnected, loadNeighbourhood, type Neighbourhood, type SimilarBy } from "$lib/neighbourhood";
    import { citationCount, primaryCategory, publishedYear, truncate } from "$lib/paper";
    import { onThemeChange, resolveColor, token, withAlpha } from "$lib/theme";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        paper: Paper;
        mode: NetworkMode;
        /** Most papers per group (references, citations, related), 0 = no limit */
        nodeLimit: number;
        highlightedAuthor: string;
        /** How the similar papers are found (related view) */
        similarBy?: SimilarBy;
        /** Papers of the open category map, the backdrop of the related view */
        context?: Paper[];
        onselect: (paper: Paper) => void;
    }

    let { paper, mode, nodeLimit, highlightedAuthor, similarBy = "content", context = [], onselect }: Props = $props();

    type Group = "selected" | "cites" | "citedBy" | "related" | "context";
    const groupNote: Record<Group, string> = {
        selected: "Selected paper",
        cites: "Cited by the selected paper",
        citedBy: "Cites the selected paper",
        related: "Similar to the selected paper",
        context: "On the map of this category",
    };

    let container = $state<HTMLDivElement>();
    let width = $state(0);
    let data = $state<Neighbourhood | null>(null);
    let error = $state<string | null>(null);
    let hovered = $state<{ paper: Paper; group: Group; x: number; y: number } | null>(null);
    let ring = $state<{ x: number; y: number; size: number } | null>(null);
    let labels = $state<PlacedLabel[]>([]);
    /** Year ticks along the top and citation ticks along the left, in px */
    let yearTicks = $state<{ year: number; left: number }[]>([]);
    let citationTicks = $state<{ label: string; top: number }[]>([]);
    let centreLine = $state<number | null>(null);
    let themeVersion = $state(0);

    $effect(() => {
        const stop = onThemeChange(() => themeVersion++);
        return stop;
    });

    $effect(() => {
        const id = paper.entry_id;
        data = null;
        error = null;
        loadNeighbourhood(id)
            .then((result) => {
                if (paper.entry_id === id) data = result;
            })
            .catch(() => {
                if (paper.entry_id === id) error = "The citation network could not be loaded.";
            });
    });

    // the similar papers: from the embedding, or connected through the citation graph
    let connected = $state<Paper[] | null>(null);
    $effect(() => {
        const id = paper.entry_id;
        const by = similarBy;
        connected = null;
        if (by === "content") return;
        loadConnected(id, by)
            .then((result) => {
                if (paper.entry_id === id && similarBy === by) connected = result.papers;
            })
            .catch(() => {
                if (paper.entry_id === id && similarBy === by) connected = [];
            });
    });
    const related = $derived(similarBy === "content" ? (data?.related ?? []) : (connected ?? []));

    /** Year with the month as a fraction, so papers of one year spread out */
    function yearOf(p: Paper): number | null {
        const year = Number(publishedYear(p.published));
        if (!year) return null;
        const date = new Date(p.published!);
        return year + (date.getMonth() + date.getDate() / 31) / 12;
    }

    /** Vertical position: citations on a log scale */
    const logCitations = (p: Paper) => Math.log10(1 + citationCount(p));

    function limit(list: Paper[]): Paper[] {
        if (!nodeLimit || list.length <= nodeLimit) return list;
        return [...list].sort((a, b) => citationCount(b) - citationCount(a)).slice(0, nodeLimit);
    }

    const groups = $derived.by(() => {
        const cites = data ? limit(data.cites) : [];
        // two papers can cite each other (a later version cites back): such a paper is drawn once, as a reference
        const drawn = new Set([paper.entry_id, ...cites.map((p) => p.entry_id)]);
        return {
            cites,
            citedBy: data ? limit(data.citedBy).filter((p) => !drawn.has(p.entry_id)) : [],
            related: limit(related).filter((p) => p.entry_id !== paper.entry_id),
        };
    });

    const legend = $derived.by(() => {
        if (!data) return [];
        const shown = mode === "citations" ? [...groups.cites, ...groups.citedBy] : groups.related;
        const counts = new Map<string, number>();
        for (const p of [data.paper, ...shown]) {
            const id = subjectOf(primaryCategory(p.categories)) || "other";
            counts.set(id, (counts.get(id) ?? 0) + 1);
        }
        return [...counts.entries()]
            .sort((a, b) => b[1] - a[1])
            .map(([id, count]) => ({
                id,
                name: id === "other" ? "Other" : subjectName(id),
                color: subjectColor(id),
                count,
            }));
    });

    interface Layout {
        graph: Graph;
        /** citations mode: graph y per log10 unit above minLog, and the year of the selected paper */
        yScale: number;
        minLog: number;
        maxLog: number;
        centreYear: number;
    }

    /** Tick label for a citation count: 1k, 10k, 100k */
    function tickLabel(value: number): string {
        if (value >= 1000) return `${value / 1000}k`;
        return String(value);
    }

    function buildGraph(n: Neighbourhood, layout: NetworkMode, aspect: number): Layout {
        const graph = new Graph({ type: "directed" });
        const centre = n.paper;
        const centreYear = yearOf(centre) ?? new Date().getFullYear();
        const shown = layout === "citations" ? [...groups.cites, ...groups.citedBy] : groups.related;
        const logs = [logCitations(centre), ...shown.map(logCitations)];
        const maxLog = Math.max(...logs);
        // the axis covers only the shown papers, which are the most cited ones
        const minLog = Math.min(maxLog - 0.5, ...logs);
        const size = (p: Paper) => 3 + 3 * (logCitations(p) / Math.max(1, maxLog));
        const yOf = (p: Paper) => (logCitations(p) - minLog) * yScale;

        let yScale = 1;
        if (layout === "citations") {
            // the year range fills the width, the citation axis the height
            const years = [centreYear, ...shown.map((p) => yearOf(p) ?? centreYear)];
            const range = Math.max(2, Math.max(...years) - Math.min(...years));
            yScale = (range * aspect) / ((maxLog - minLog) * 1.15);
        }

        graph.addNode(centre.entry_id, {
            x: layout === "citations" ? centreYear : centre.x,
            y: layout === "citations" ? yOf(centre) : centre.y,
            size: size(centre) + 3,
            color: resolveColor(categoryColor(centre.categories)),
            zIndex: 3,
        });

        const add = (p: Paper, x: number, y: number) => {
            if (graph.hasNode(p.entry_id)) return;
            graph.addNode(p.entry_id, { x, y, size: size(p), color: withAlpha(resolveColor(categoryColor(p.categories)), 0.85), zIndex: 1 });
        };

        if (layout === "citations") {
            // the links all lead to the selected paper, they are drawn only for the hovered point
            const edge = { type: "arrow", size: 1.2, color: token("--map-edge", "rgba(0,0,0,0.3)") };
            for (const p of groups.cites) {
                add(p, yearOf(p) ?? centreYear - 1, yOf(p));
                graph.addEdge(centre.entry_id, p.entry_id, edge);
            }
            for (const p of groups.citedBy) {
                add(p, yearOf(p) ?? centreYear + 1, yOf(p));
                if (!graph.hasEdge(p.entry_id, centre.entry_id)) graph.addEdge(p.entry_id, centre.entry_id, edge);
            }
        } else {
            groups.related.forEach((p, i) => {
                const hasPosition = p.x !== 0 || p.y !== 0;
                // papers without a map position go on a ring around the centre
                const angle = (i / Math.max(groups.related.length, 1)) * Math.PI * 2;
                add(p, hasPosition ? p.x : centre.x + Math.cos(angle), hasPosition ? p.y : centre.y + Math.sin(angle));
            });
        }
        return { graph, yScale, minLog, maxLog, centreYear };
    }

    function updateAxes(renderer: Sigma, n: Neighbourhood, layout: Layout) {
        if (mode !== "citations") {
            yearTicks = [];
            citationTicks = [];
            centreLine = null;
            return;
        }
        const years = [n.paper, ...groups.cites, ...groups.citedBy]
            .map((p) => Number(publishedYear(p.published)))
            .filter(Boolean);
        if (!years.length) return;
        const min = Math.min(...years);
        const max = Math.max(...years) + 1;
        const step = max - min > 24 ? 5 : max - min > 10 ? 2 : 1;
        const nextYears: { year: number; left: number }[] = [];
        for (let year = Math.ceil(min / step) * step; year <= max; year += step) {
            nextYears.push({ year, left: renderer.graphToViewport({ x: year, y: 0 }).x });
        }
        yearTicks = nextYears;

        // ticks at 1, 2, 5 × 10^k inside the shown range, only the powers of ten when there are enough
        const inRange = (value: number) =>
            Math.log10(1 + value) >= layout.minLog - 0.02 && Math.log10(1 + value) <= layout.maxLog + 0.02;
        const powers = [1, 10, 100, 1000, 10000, 100000, 1000000].filter(inRange);
        const values =
            powers.length >= 3
                ? powers
                : [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000].filter(inRange);
        citationTicks = values.map((value) => ({
            label: tickLabel(value),
            top: renderer.graphToViewport({
                x: layout.centreYear,
                y: (Math.log10(1 + value) - layout.minLog) * layout.yScale,
            }).y,
        }));
        centreLine = renderer.graphToViewport({ x: layout.centreYear, y: 0 }).x;
    }

    let renderer: Sigma | null = null;
    let resetView = () => {};

    $effect(() => {
        const n = data;
        const el = container;
        void themeVersion;
        if (!n || !el) return;

        const info = new Map<string, { paper: Paper; group: Group }>([
            [n.paper.entry_id, { paper: n.paper, group: "selected" }],
        ]);
        for (const p of n.cites) info.set(p.entry_id, { paper: p, group: "cites" });
        for (const p of n.citedBy) if (!info.has(p.entry_id)) info.set(p.entry_id, { paper: p, group: "citedBy" });
        for (const p of related) if (!info.has(p.entry_id)) info.set(p.entry_id, { paper: p, group: "related" });

        const stage = { width: el.clientWidth || 1, height: el.clientHeight || 1 };
        const layout = buildGraph(n, mode, stage.height / stage.width);
        const graph = layout.graph;
        const dim = token("--map-dim", "rgba(0,0,0,0.1)");

        // related view: the view is fitted to the related papers, the category map lies behind them
        let focus: { x: [number, number]; y: [number, number] } | null = null;
        if (mode === "related" && context.length) {
            const xs: number[] = [];
            const ys: number[] = [];
            graph.forEachNode((_, a) => {
                xs.push(a.x);
                ys.push(a.y);
            });
            const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 0.5);
            const pad = span * 0.5;
            focus = {
                x: [Math.min(...xs) - pad, Math.max(...xs) + pad],
                y: [Math.min(...ys) - pad, Math.max(...ys) + pad],
            };
            const backdrop = token("--border-strong", "#b9bdc9");
            for (const p of context) {
                if (graph.hasNode(p.entry_id) || (p.x === 0 && p.y === 0)) continue;
                graph.addNode(p.entry_id, { x: p.x, y: p.y, size: 3.5, color: backdrop, zIndex: 0 });
                info.set(p.entry_id, { paper: p, group: "context" });
            }
        }
        const author = highlightedAuthor.toLowerCase();
        let hoveredId: string | null = null;

        // titles go to the selected paper and then to the most cited ones that fit
        const shown = mode === "citations" ? [...groups.cites, ...groups.citedBy] : groups.related;
        const ranked = [
            n.paper,
            ...shown
                .filter((p) => !author || p.authors.toLowerCase().includes(author))
                .sort((a, b) => citationCount(b) - citationCount(a)),
        ].map((p) => ({ id: p.entry_id, label: truncate(p.title, 90) }));

        const r = new Sigma(graph, el, {
            // titles are HTML elements placed by lib/labels.ts
            renderLabels: false,
            // a stage without size (hidden, or a window dragged very small) is no error
            allowInvalidContainer: true,
            renderEdgeLabels: false,
            defaultEdgeType: "arrow",
            zIndex: true,
            stagePadding: 64,
            minCameraRatio: 0.05,
            maxCameraRatio: 3,
            nodeReducer: (node, attrs) => {
                const item = info.get(node);
                if (!author || !item || item.group === "selected" || item.group === "context") return attrs;
                const match = item.paper.authors.toLowerCase().includes(author);
                return match ? { ...attrs, size: attrs.size + 2, zIndex: 2 } : { ...attrs, color: dim, zIndex: 0 };
            },
            // only the hovered point shows its link to the selected paper
            edgeReducer: (edge, attrs) => ({ ...attrs, hidden: !hoveredId || !graph.hasExtremity(edge, hoveredId) }),
        });

        if (focus) r.setCustomBBox(focus);

        // sigma fits the graph into the shorter side of the stage, for the
        // chart the year axis should span the full width instead
        const fit = { x: 0.5, y: 0.5, angle: 0, ratio: mode === "citations" ? Math.min(1, stage.height / stage.width) : 1 };
        r.getCamera().setState(fit);
        resetView = () => r.getCamera().animate(fit, { duration: 300 });

        const updateRing = () => {
            const d = r.getNodeDisplayData(n.paper.entry_id);
            if (!d) return;
            const pos = r.framedGraphToViewport(d);
            ring = { x: pos.x, y: pos.y, size: r.scaleSize(d.size) * 2 + 8 };
        };

        r.on("enterNode", ({ node, event }) => {
            const item = info.get(node);
            if (item) hovered = { ...item, x: event.x, y: event.y };
            hoveredId = node;
            el.style.cursor = "pointer";
            r.refresh({ skipIndexation: true });
        });
        r.on("moveBody", ({ event }) => {
            if (hovered) hovered = { ...hovered, x: event.x, y: event.y };
        });
        r.on("leaveNode", () => {
            hovered = null;
            hoveredId = null;
            el.style.cursor = "";
            r.refresh({ skipIndexation: true });
        });
        r.on("clickNode", ({ node }) => {
            const item = info.get(node);
            if (item && item.group !== "selected") onselect(item.paper);
        });

        const placer = createLabelPlacer(r, 60, () => overlayBoxes(el));
        let needsLabels = true;
        r.getCamera().on("updated", () => {
            needsLabels = true;
            updateAxes(r, n, layout);
            updateRing();
        });
        r.on("afterRender", () => {
            updateRing();
            if (!needsLabels) return;
            needsLabels = false;
            labels = placer.place(ranked);
        });
        // sigma already rendered once in its constructor, render again so the titles get placed
        r.refresh();
        updateAxes(r, n, layout);
        renderer = r;

        return () => {
            r.kill();
            renderer = null;
            hovered = null;
            ring = null;
            labels = [];
            yearTicks = [];
            citationTicks = [];
            centreLine = null;
        };
    });

    const camera = () => renderer?.getCamera();
</script>

<div class="network" bind:clientWidth={width}>
    <div class="canvas" bind:this={container}></div>

    {#if mode === "citations" && data}
        <div class="axes" aria-hidden="true">
            {#each citationTicks as tick (tick.label)}
                <span class="row" style:top="{tick.top}px"><em>{tick.label}</em></span>
            {/each}
            {#each yearTicks as tick (tick.year)}
                <span class="column" style:left="{tick.left}px"><em>{tick.year}</em></span>
            {/each}
            {#if centreLine !== null}
                <span class="centre" style:left="{centreLine}px"></span>
            {/if}
            <span class="axis-title">citations ↑</span>
        </div>
    {/if}

    {#each labels as item (item.id)}
        <span
            class="node-label"
            class:primary={item.id === paper.entry_id}
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

    {#if error}
        <p class="state">{error}</p>
    {:else if !data}
        <div class="state"><Spinner size={24} /></div>
    {:else if mode === "citations" && groups.cites.length + groups.citedBy.length === 0}
        <p class="state">None of this paper's references or citations are in the dataset.</p>
    {:else if mode === "related" && groups.related.length === 0}
        <p class="state">No similar papers are known for this paper.</p>
    {/if}

    {#if hovered}
        <HoverCard paper={hovered.paper} x={hovered.x} y={hovered.y} {width} note={groupNote[hovered.group]} />
    {/if}

    {#if data}
        <div class="legend">
            {#if mode === "citations"}
                <span class="hint">
                    {#if data.citesTotal}<b>{groups.cites.length}</b> of {data.citesTotal.toLocaleString("en")} references ·{/if}
                    {#if data.citedByTotal}<b>{groups.citedBy.length}</b> of {data.citedByTotal.toLocaleString("en")} citations ·{/if}
                    hover a point for its link
                </span>
            {:else}
                <span class="hint">
                    <b>{groups.related.length}</b>
                    {similarBy === "references"
                        ? "papers sharing references"
                        : similarBy === "citations"
                          ? "papers cited together with it"
                          : data.relatedBasis === "embedding"
                            ? "nearest papers in the embedding"
                            : data.relatedBasis === "map"
                              ? "nearest papers on the map (rough guide, no embedding for this paper)"
                              : "papers recommended by Semantic Scholar"}, at their map positions{context.length
                        ? " · grey: the other papers of this category"
                        : ""}
                </span>
            {/if}
            {#each legend as item (item.id)}
                <span><i style:background={item.color}></i>{item.name} <b>{item.count}</b></span>
            {/each}
        </div>
    {/if}

    <ZoomControls
        onzoomin={() => camera()?.animatedZoom({ duration: 200 })}
        onzoomout={() => camera()?.animatedUnzoom({ duration: 200 })}
        onreset={() => resetView()}
    />
</div>

<style>
    .network {
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
    .state {
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        margin: 0;
        color: var(--text-3);
        pointer-events: none;
    }
    .ring {
        position: absolute;
        transform: translate(-50%, -50%);
        border: 2px solid var(--text);
        border-radius: 50%;
        pointer-events: none;
    }

    .axes {
        position: absolute;
        inset: 0;
        pointer-events: none;
    }
    .axes em {
        position: absolute;
        color: var(--text-3);
        font-variant-numeric: tabular-nums;
        font-size: var(--text-xs);
        font-style: normal;
        white-space: nowrap;
    }
    .row {
        position: absolute;
        left: 0;
        right: 0;
        border-top: 1px dashed var(--map-grid);
    }
    .row em {
        left: 8px;
        top: 2px;
    }
    .column {
        position: absolute;
        top: 0;
        bottom: 0;
        border-left: 1px dashed var(--map-grid);
    }
    .column em {
        top: 8px;
        transform: translateX(-50%);
    }
    .centre {
        position: absolute;
        top: 0;
        bottom: 0;
        border-left: 1px solid var(--border-strong);
    }
    .axis-title {
        position: absolute;
        left: 8px;
        top: 28px;
        color: var(--text-3);
        font-size: var(--text-xs);
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
        color: var(--text);
        font-variant-numeric: tabular-nums;
        font-weight: 500;
    }
    .legend .hint {
        display: inline;
        color: var(--text-3);
    }
</style>
