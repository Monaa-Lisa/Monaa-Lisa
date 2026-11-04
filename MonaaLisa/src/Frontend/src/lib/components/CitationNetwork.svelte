<!--
  The network around one paper, drawn with Sigma.js. Two layouts:

  citations  x = publication year. The papers it cites sit mostly to the left
             (older), the papers citing it to the right (newer), so the graph
             reads as a timeline of where the work comes from and where it went.
  related    the related papers at their real UMAP positions around the
             selected paper, i.e. its semantic neighbourhood on the map.
-->
<script module lang="ts">
    export type NetworkMode = "citations" | "related";
</script>

<script lang="ts">
    import Graph from "graphology";
    import Sigma from "sigma";
    import Spinner from "$lib/components/ui/Spinner.svelte";
    import { categoryColor } from "$lib/categories";
    import { loadNeighbourhood, type Neighbourhood } from "$lib/neighbourhood";
    import { publishedYear, shortAuthors } from "$lib/paper";
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

    // read the colours from the design tokens so CSS stays the single source
    function token(name: string, fallback: string): string {
        if (typeof document === "undefined") return fallback;
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
    }
    const COLORS = {
        cites: token("--cites", "#e07a5f"),
        citedBy: token("--cited-by", "#5fb3a5"),
        selected: token("--accent", "#c9a25e"),
        dim: "#2e2e35",
        edge: "#34343c",
        label: token("--text-2", "#a6a6b0"),
    };

    type Group = "selected" | "cites" | "citedBy" | "related";
    interface NodeInfo {
        paper: Paper;
        group: Group;
    }

    let container: HTMLDivElement;
    let data = $state<Neighbourhood | null>(null);
    let error = $state<string | null>(null);
    let hovered = $state<NodeInfo | null>(null);
    let ticks = $state<{ year: number; left: number }[]>([]);

    $effect(() => {
        const id = paper.entry_id;
        data = null;
        error = null;
        loadNeighbourhood(id)
            .then((result) => {
                if (paper.entry_id === id) data = result;
            })
            .catch(() => {
                if (paper.entry_id === id) error = "The network could not be loaded.";
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
    function jitter(id: string, salt = 0): number {
        let h = 2166136261 ^ salt;
        for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
        return ((h >>> 0) % 10000) / 5000 - 1;
    }

    function importance(p: Paper): number {
        return p.citations.length + p.non_arxiv_citation_count;
    }

    function nodeSize(p: Paper): number {
        return 3 + Math.min(Math.log1p(importance(p)) * 1.3, 9);
    }

    function limit(list: Paper[]): Paper[] {
        if (!nodeLimit || list.length <= nodeLimit) return list;
        return [...list].sort((a, b) => importance(b) - importance(a)).slice(0, nodeLimit);
    }

    function buildGraph(n: Neighbourhood, layout: NetworkMode): Graph {
        const graph = new Graph();
        const centre = n.paper;
        const centreYear = yearOf(centre) ?? new Date().getFullYear();

        graph.addNode(centre.entry_id, {
            x: layout === "citations" ? centreYear : centre.tsne1,
            y: layout === "citations" ? 0 : centre.tsne2,
            size: 12,
            color: COLORS.selected,
            label: centre.title.length > 60 ? `${centre.title.slice(0, 60)}…` : centre.title,
            forceLabel: true,
            zIndex: 2,
        });

        const add = (p: Paper, group: Group, x: number, y: number, color: string) => {
            if (graph.hasNode(p.entry_id)) return;
            graph.addNode(p.entry_id, { x, y, size: nodeSize(p), color, label: p.title, zIndex: 1, group });
            // edge in the colour of its group, mostly transparent
            const edgeColor = color.startsWith("#") && color.length === 7 ? `${color}40` : COLORS.edge;
            graph.addEdge(centre.entry_id, p.entry_id, { color: edgeColor, size: 0.7 });
        };

        if (layout === "citations") {
            // vertical room grows with the number of nodes, years stay on the x axis
            const all = [...limit(n.cites), ...limit(n.citedBy)];
            const spread = Math.max(2, Math.sqrt(all.length) * 0.9);
            for (const p of limit(n.cites)) {
                add(p, "cites", yearOf(p) ?? centreYear - 1, jitter(p.entry_id) * spread, COLORS.cites);
            }
            for (const p of limit(n.citedBy)) {
                add(p, "citedBy", yearOf(p) ?? centreYear + 1, jitter(p.entry_id) * spread, COLORS.citedBy);
            }
        } else {
            const related = limit(n.related);
            related.forEach((p, i) => {
                const hasPosition = p.tsne1 !== 0 || p.tsne2 !== 0;
                // papers without a map position go on a ring around the centre
                const angle = (i / Math.max(related.length, 1)) * Math.PI * 2;
                const x = hasPosition ? p.tsne1 : centre.tsne1 + Math.cos(angle);
                const y = hasPosition ? p.tsne2 : centre.tsne2 + Math.sin(angle);
                add(p, "related", x, y, categoryColor(p.categories));
            });
        }
        return graph;
    }

    function updateTicks(renderer: Sigma, n: Neighbourhood) {
        if (mode !== "citations") {
            ticks = [];
            return;
        }
        const years = [n.paper, ...n.cites, ...n.citedBy]
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

    $effect(() => {
        if (!data || !container) return;
        const n = data;
        const graph = buildGraph(n, mode);
        const info = new Map<string, NodeInfo>([[n.paper.entry_id, { paper: n.paper, group: "selected" }]]);
        for (const p of n.cites) info.set(p.entry_id, { paper: p, group: "cites" });
        for (const p of n.citedBy) if (!info.has(p.entry_id)) info.set(p.entry_id, { paper: p, group: "citedBy" });
        for (const p of n.related) if (!info.has(p.entry_id)) info.set(p.entry_id, { paper: p, group: "related" });

        const author = highlightedAuthor.toLowerCase();
        const renderer = new Sigma(graph, container, {
            renderEdgeLabels: false,
            labelFont: "IBM Plex Sans, system-ui, sans-serif",
            labelSize: 11,
            labelWeight: "500",
            labelColor: { color: COLORS.label },
            labelRenderedSizeThreshold: 10,
            defaultEdgeType: "line",
            zIndex: true,
            stagePadding: 48,
            minCameraRatio: 0.05,
            maxCameraRatio: 4,
            nodeReducer: (node, attrs) => {
                const item = info.get(node);
                if (!author || !item || item.group === "selected") return attrs;
                const match = item.paper.authors.toLowerCase().includes(author);
                return match
                    ? { ...attrs, size: attrs.size + 2, zIndex: 2, forceLabel: true }
                    : { ...attrs, color: COLORS.dim, label: "" };
            },
        });

        renderer.on("enterNode", ({ node }) => {
            hovered = info.get(node) ?? null;
            container.style.cursor = "pointer";
        });
        renderer.on("leaveNode", () => {
            hovered = null;
            container.style.cursor = "";
        });
        renderer.on("clickNode", ({ node }) => {
            const item = info.get(node);
            if (item && item.group !== "selected") onselect(item.paper);
        });
        renderer.getCamera().on("updated", () => updateTicks(renderer, n));
        updateTicks(renderer, n);

        return () => {
            renderer.kill();
            hovered = null;
        };
    });

    const counts = $derived({
        cites: Math.min(data?.cites.length ?? 0, nodeLimit || Infinity),
        citedBy: Math.min(data?.citedBy.length ?? 0, nodeLimit || Infinity),
        related: Math.min(data?.related.length ?? 0, nodeLimit || Infinity),
    });

    const groupLabel: Record<Group, string> = {
        selected: "Selected paper",
        cites: "Cited by the selected paper",
        citedBy: "Cites the selected paper",
        related: "Related paper",
    };
</script>

<div class="network">
    <div class="canvas" bind:this={container}></div>

    {#if error}
        <p class="state">{error}</p>
    {:else if !data}
        <div class="state"><Spinner size={24} /></div>
    {:else if mode === "citations" && counts.cites + counts.citedBy === 0}
        <p class="state">No citations or references of this paper are in the dataset.</p>
    {:else if mode === "related" && counts.related === 0}
        <p class="state">No related papers known for this paper.</p>
    {/if}

    {#if ticks.length}
        <div class="axis" aria-hidden="true">
            {#each ticks as tick (tick.year)}
                <span style:left="{tick.left}px">{tick.year}</span>
            {/each}
        </div>
    {/if}

    {#if data}
        <div class="legend card">
            <span><i style:background={COLORS.selected}></i>Selected</span>
            {#if mode === "citations"}
                <span><i style:background={COLORS.cites}></i>Cites <b>{counts.cites}</b></span>
                <span><i style:background={COLORS.citedBy}></i>Cited by <b>{counts.citedBy}</b></span>
                <span class="hint">x axis: year published</span>
            {:else}
                <span><i class="multi"></i>Related <b>{counts.related}</b></span>
                <span class="hint">positions: semantic map (UMAP)</span>
            {/if}
        </div>
    {/if}

    {#if hovered}
        <div class="tooltip card">
            <span class="group">{groupLabel[hovered.group]}</span>
            <strong>{hovered.paper.title}</strong>
            <span class="meta">
                {shortAuthors(hovered.paper.authors)}{publishedYear(hovered.paper.published)
                    ? ` · ${publishedYear(hovered.paper.published)}`
                    : ""}
            </span>
        </div>
    {/if}
</div>

<style>
    .network {
        position: relative;
        width: 100%;
        height: 100%;
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

    .axis {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 64px;
        height: 16px;
        pointer-events: none;
    }
    .axis span {
        position: absolute;
        transform: translateX(-50%);
        color: var(--text-3);
        font-family: var(--font-mono);
        font-size: var(--text-xs);
    }

    .legend {
        position: absolute;
        left: 12px;
        bottom: 12px;
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 8px 12px;
        color: var(--text-2);
        font-size: var(--text-xs);
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
    .legend i.multi {
        background: conic-gradient(#f72585, #4cc9f0, #ffd166, #2ec4b6, #f72585);
    }
    .legend b {
        color: var(--text);
        font-family: var(--font-mono);
        font-weight: 500;
    }
    .legend .hint {
        color: var(--text-3);
        padding-left: 12px;
        border-left: 1px solid var(--border);
    }

    .tooltip {
        position: absolute;
        left: 50%;
        top: 12px;
        transform: translateX(-50%);
        display: grid;
        gap: 4px;
        max-width: 420px;
        padding: 10px 14px;
        pointer-events: none;
    }
    .tooltip .group {
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .tooltip strong {
        color: var(--text);
        font-size: var(--text-sm);
        font-weight: 500;
        line-height: 1.35;
    }
    .tooltip .meta {
        color: var(--text-2);
        font-size: var(--text-xs);
    }
</style>
