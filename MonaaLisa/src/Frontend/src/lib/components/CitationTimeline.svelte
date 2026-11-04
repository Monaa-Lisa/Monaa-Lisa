<!--
  The citation neighbourhood of one paper, drawn with Sigma.js. Two layouts:

  citations  x = year of publication. The papers it cites are to the left
             (older), the papers citing it to the right (newer). Arrows point
             from the citing paper to the cited paper.
  related    the related papers (Semantic Scholar) at their map positions
             around the selected paper, i.e. its neighbourhood on the map.

  Nodes are coloured by subject like everywhere else, so citations from other
  fields stand out.
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
    import { CATEGORY_COLORS, categoryColor, subjectName, subjectOf } from "$lib/categories";
    import { loadNeighbourhood, type Neighbourhood } from "$lib/neighbourhood";
    import { citationCount, primaryCategory, publishedYear, truncate } from "$lib/paper";
    import { onThemeChange, token } from "$lib/theme";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        paper: Paper;
        mode: NetworkMode;
        /** Most nodes per group, 0 = no limit */
        nodeLimit: number;
        highlightedAuthor: string;
        onselect: (paper: Paper) => void;
    }

    let { paper, mode, nodeLimit, highlightedAuthor, onselect }: Props = $props();

    type Group = "selected" | "cites" | "citedBy" | "related";
    const groupNote: Record<Group, string> = {
        selected: "Selected paper",
        cites: "Cited by the selected paper",
        citedBy: "Cites the selected paper",
        related: "Related to the selected paper",
    };

    let container = $state<HTMLDivElement>();
    let width = $state(0);
    let data = $state<Neighbourhood | null>(null);
    let error = $state<string | null>(null);
    let hovered = $state<{ paper: Paper; group: Group; x: number; y: number } | null>(null);
    let ring = $state<{ x: number; y: number; size: number } | null>(null);
    let ticks = $state<{ year: number; left: number }[]>([]);
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

    function yearOf(p: Paper): number | null {
        const year = Number(publishedYear(p.published));
        if (!year) return null;
        // spread papers of the same year over the year
        const date = new Date(p.published!);
        return year + (date.getMonth() + date.getDate() / 31) / 12;
    }

    /** Stable pseudo random value in [-1, 1] per paper, so layouts do not jump */
    function jitter(id: string): number {
        let h = 2166136261;
        for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
        return ((h >>> 0) % 10000) / 5000 - 1;
    }

    function limit(list: Paper[]): Paper[] {
        if (!nodeLimit || list.length <= nodeLimit) return list;
        return [...list].sort((a, b) => citationCount(b) - citationCount(a)).slice(0, nodeLimit);
    }

    const groups = $derived({
        cites: data ? limit(data.cites) : [],
        citedBy: data ? limit(data.citedBy) : [],
        related: data ? limit(data.related) : [],
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
                color: CATEGORY_COLORS[id] ?? token("--text-3", "#888"),
                count,
            }));
    });

    function buildGraph(n: Neighbourhood, layout: NetworkMode, maxCitations: number, aspect: number): Graph {
        const graph = new Graph({ type: "directed" });
        const centre = n.paper;
        const centreYear = yearOf(centre) ?? new Date().getFullYear();
        const size = (p: Paper) => 3 + 6 * (Math.log1p(citationCount(p)) / Math.log1p(maxCitations));
        const edge = { type: "arrow", size: 1, color: token("--map-edge", "rgba(0,0,0,0.3)") };

        graph.addNode(centre.entry_id, {
            x: layout === "citations" ? centreYear : centre.x,
            y: layout === "citations" ? 0 : centre.y,
            size: size(centre) + 2,
            color: categoryColor(centre.categories),
            label: truncate(centre.title, 70),
            forceLabel: true,
            zIndex: 3,
        });

        const add = (p: Paper, x: number, y: number, labelled: boolean) => {
            if (graph.hasNode(p.entry_id)) return;
            graph.addNode(p.entry_id, {
                x,
                y,
                size: size(p),
                color: categoryColor(p.categories),
                label: truncate(p.title, 70),
                forceLabel: labelled,
                zIndex: 1,
            });
        };
        // the most cited papers of each group always carry their title
        const labelled = (list: Paper[]) =>
            new Set(
                [...list]
                    .sort((a, b) => citationCount(b) - citationCount(a))
                    .slice(0, 4)
                    .map((p) => p.entry_id),
            );

        if (layout === "citations") {
            const all = [...groups.cites, ...groups.citedBy];
            // the year range fills the width, the vertical room follows the stage's shape
            const years = [centreYear, ...all.map((p) => yearOf(p) ?? centreYear)];
            const range = Math.max(2, Math.max(...years) - Math.min(...years));
            const spread = (range * aspect) / 2;
            const topCites = labelled(groups.cites);
            const topCitedBy = labelled(groups.citedBy);
            for (const p of groups.cites) {
                add(p, yearOf(p) ?? centreYear - 1, jitter(p.entry_id) * spread, topCites.has(p.entry_id));
                graph.addEdge(centre.entry_id, p.entry_id, edge);
            }
            for (const p of groups.citedBy) {
                add(p, yearOf(p) ?? centreYear + 1, jitter(p.entry_id) * spread, topCitedBy.has(p.entry_id));
                if (!graph.hasEdge(p.entry_id, centre.entry_id)) graph.addEdge(p.entry_id, centre.entry_id, edge);
            }
        } else {
            const top = labelled(groups.related);
            groups.related.forEach((p, i) => {
                const hasPosition = p.x !== 0 || p.y !== 0;
                // papers without a map position go on a ring around the centre
                const angle = (i / Math.max(groups.related.length, 1)) * Math.PI * 2;
                add(
                    p,
                    hasPosition ? p.x : centre.x + Math.cos(angle),
                    hasPosition ? p.y : centre.y + Math.sin(angle),
                    top.has(p.entry_id),
                );
            });
        }
        return graph;
    }

    function updateTicks(renderer: Sigma, n: Neighbourhood) {
        if (mode !== "citations") {
            ticks = [];
            return;
        }
        const years = [n.paper, ...groups.cites, ...groups.citedBy]
            .map((p) => Number(publishedYear(p.published)))
            .filter(Boolean);
        if (!years.length) return;
        const min = Math.min(...years);
        const max = Math.max(...years) + 1;
        const step = max - min > 24 ? 5 : max - min > 10 ? 2 : 1;
        const next: { year: number; left: number }[] = [];
        for (let year = Math.ceil(min / step) * step; year <= max; year += step) {
            next.push({ year, left: renderer.graphToViewport({ x: year, y: 0 }).x });
        }
        ticks = next;
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
        for (const p of n.related) if (!info.has(p.entry_id)) info.set(p.entry_id, { paper: p, group: "related" });

        const maxCitations = Math.max(1, ...[...info.values()].map((i) => citationCount(i.paper)));
        const stage = { width: el.clientWidth || 1, height: el.clientHeight || 1 };
        const graph = buildGraph(n, mode, maxCitations, stage.height / stage.width);
        const dim = token("--map-dim", "rgba(0,0,0,0.1)");
        const author = highlightedAuthor.toLowerCase();

        const r = new Sigma(graph, el, {
            renderEdgeLabels: false,
            labelFont: "IBM Plex Sans, system-ui, sans-serif",
            labelSize: 11,
            labelWeight: "500",
            labelColor: { color: token("--map-label", "#1c1c1c") },
            labelRenderedSizeThreshold: 7,
            labelDensity: 0.3,
            labelGridCellSize: 150,
            defaultEdgeType: "arrow",
            zIndex: true,
            stagePadding: 64,
            minCameraRatio: 0.05,
            maxCameraRatio: 3,
            nodeReducer: (node, attrs) => {
                const item = info.get(node);
                if (!author || !item || item.group === "selected") return attrs;
                const match = item.paper.authors.toLowerCase().includes(author);
                return match
                    ? { ...attrs, size: attrs.size + 2, zIndex: 2, forceLabel: true }
                    : { ...attrs, color: dim, label: "", zIndex: 0 };
            },
        });

        // sigma fits the graph into the shorter side of the stage, for the
        // timeline the year axis should span the full width instead
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
            const item = info.get(node);
            if (item && item.group !== "selected") onselect(item.paper);
        });
        r.getCamera().on("updated", () => {
            updateTicks(r, n);
            updateRing();
        });
        r.on("afterRender", updateRing);
        updateTicks(r, n);
        renderer = r;

        return () => {
            r.kill();
            renderer = null;
            hovered = null;
            ring = null;
            ticks = [];
        };
    });

    const camera = () => renderer?.getCamera();
</script>

<div class="network" bind:clientWidth={width}>
    <div class="canvas" bind:this={container}></div>

    {#if ticks.length}
        <div class="axis" aria-hidden="true">
            {#each ticks as tick (tick.year)}
                <span class="tick" style:left="{tick.left}px"><em>{tick.year}</em></span>
            {/each}
        </div>
    {/if}

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
        <p class="state">No related papers are known for this paper.</p>
    {/if}

    {#if hovered}
        <HoverCard paper={hovered.paper} x={hovered.x} y={hovered.y} {width} note={groupNote[hovered.group]} />
    {/if}

    {#if data}
        <div class="legend">
            {#if mode === "citations"}
                <span class="hint">
                    ← <b>{groups.cites.length}</b> references · <b>{groups.citedBy.length}</b> citations → · x: year of
                    publication · arrows: citing → cited
                </span>
            {:else}
                <span class="hint"><b>{groups.related.length}</b> related papers at their map positions</span>
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

    .axis {
        position: absolute;
        inset: 0;
        pointer-events: none;
    }
    .tick {
        position: absolute;
        top: 0;
        bottom: 0;
        border-left: 1px dashed var(--map-grid);
    }
    .tick em {
        position: absolute;
        top: 8px;
        transform: translateX(-50%);
        color: var(--text-3);
        font-family: var(--font-mono);
        font-size: var(--text-xs);
        font-style: normal;
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
        font-family: var(--font-mono);
        font-weight: 500;
    }
    .legend .hint {
        display: inline;
        color: var(--text-3);
    }
</style>
