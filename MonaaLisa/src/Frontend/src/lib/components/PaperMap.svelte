<!--
  The paper map of one category, drawn with Sigma.js.

  Every point is a paper at its UMAP position (a fixed projection of the
  SPECTER2 embedding of title and abstract), so papers on similar topics sit
  close together. Point size follows the citation count, colour either the
  primary category of the paper (the three most common ones on this map, the
  rest is grey) or its year of publication (`colorBy`).

  The regions of the map are named after the terms typical for the titles of
  their papers (lib/regions.ts, `showRegions`). After zooming in, the papers
  in view are grouped and named again, so the names get more specific.

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
    import { loadNeighbourhood } from "$lib/neighbourhood";
    import { createLabelPlacer, overlayBoxes, type Box, type PlacedLabel } from "$lib/labels";
    import { findRegions, type Region } from "$lib/regions";
    import type { MapScene } from "$lib/exportMap";
    import { citationCount, primaryCategory, publishedYear, truncate } from "$lib/paper";
    import { onThemeChange, resolveColor, token, withAlpha } from "$lib/theme";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        papers: Paper[];
        /** Papers to emphasise, everything else is dimmed. null = no highlight. */
        highlight: Paper[] | null;
        selected: Paper | null;
        colorBy: ColorBy;
        /** Ids of the papers saved in the library, marked with a star on the map */
        saved?: string[];
        /** Time-lapse: only papers published up to this year are shown, null = all */
        untilYear?: number | null;
        /** Name the regions of the map */
        showRegions: boolean;
        onselect: (paper: Paper) => void;
    }

    let { papers, highlight, selected, colorBy, showRegions, untilYear = null, saved = [], onselect }: Props = $props();

    let container = $state<HTMLDivElement>();
    let width = $state(0);
    let hovered = $state<{ paper: Paper; x: number; y: number } | null>(null);
    let ring = $state<{ x: number; y: number; size: number } | null>(null);
    let labels = $state<PlacedLabel[]>([]);
    let stars = $state<{ id: string; x: number; y: number }[]>([]);
    /** Copy of `saved` for the renderer's callbacks, which must not be tracked */
    let savedIds: string[] = [];
    let regionLabels = $state<{ id: string; label: string; x: number; y: number }[]>([]);

    const yearOf = (p: Paper) => Number(publishedYear(p.published)) || 0;
    // the regions are named from the papers shown, so the names change as the time-lapse runs
    const regions = $derived(findRegions(untilYear ? papers.filter((p) => yearOf(p) <= untilYear) : papers));
    /** Copy of `untilYear` for the renderer's callbacks, which must not be tracked */
    let hideAfter: number | null = null;
    const hiddenByYear = (p: Paper | undefined) => !!hideAfter && !!p && yearOf(p) > hideAfter;
    /** Regions of the papers in view after zooming in, null = the regions of the whole map */
    let zoomRegions = $state<Region[] | null>(null);
    /** Zoomed in further than this, the names come from the papers in view */
    const ZOOM_NAMES_BELOW = 0.7;

    /** Must match .region-label in app.css */
    const REGION_FONT = '600 14px "IBM Plex Sans", system-ui, sans-serif';
    const REGION_HEIGHT = 20;
    const measure = typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d");

    /**
     * Puts the region names at the centres of their regions, the largest
     * regions first, and leaves out a name that would touch another one or
     * an overlay. Returns the boxes taken, the paper titles keep clear of them.
     */
    function placeRegions(r: Sigma, blocked: Box[]): Box[] {
        const taken: Box[] = [];
        const placed: typeof regionLabels = [];
        if (showRegions && measure) {
            measure.font = REGION_FONT;
            const { width: stageWidth, height: stageHeight } = r.getDimensions();
            for (const region of [...(zoomRegions ?? regions)].sort((a, b) => b.size - a.size)) {
                const p = r.graphToViewport(region);
                const half = measure.measureText(region.label).width / 2 + 8;
                const box: Box = [p.x - half, p.y - REGION_HEIGHT / 2, p.x + half, p.y + REGION_HEIGHT / 2];
                if (box[0] < 0 || box[1] < 0 || box[2] > stageWidth || box[3] > stageHeight) continue;
                const hits = (b: Box) => b[0] < box[2] && box[0] < b[2] && b[1] < box[3] && box[1] < b[3];
                if (blocked.some(hits) || taken.some(hits)) continue;
                taken.push(box);
                placed.push({ id: region.id, label: region.label, x: p.x, y: p.y });
            }
        }
        regionLabels = placed;
        return taken;
    }
    let themeVersion = $state(0);

    /** Smallest and largest citation count on the map, as log1p */
    const citationRange = $derived.by((): [number, number] => {
        let lo = Infinity;
        let hi = 0;
        for (const p of papers) {
            const c = Math.log1p(citationCount(p));
            if (c < lo) lo = c;
            if (c > hi) hi = c;
        }
        return [Number.isFinite(lo) ? lo : 0, hi];
    });

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
     * Bounding box of the bulk of the papers: the initial view leaves out
     * the outermost 1.5 % on every side. A handful of far away points would
     * otherwise shrink the map to the middle of the stage; they are still
     * there when zooming out.
     */
    function robustBBox(list: Paper[]): { x: [number, number]; y: [number, number] } | null {
        if (list.length < 10) return null;
        const range = (values: number[]): [number, number] => {
            const sorted = [...values].sort((a, b) => a - b);
            const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
            const lo = q(0.015);
            const hi = q(0.985);
            const pad = (hi - lo) * 0.04 || 1;
            return [lo - pad, hi + pad];
        };
        return { x: range(list.map((p) => p.x)), y: range(list.map((p) => p.y)) };
    }

    /**
     * Point radius from 3.5 to 11 px over the citation range of the papers
     * shown (log scale). The curve keeps most points small, so the few very
     * often cited papers stand out.
     */
    function nodeSize(p: Paper): number {
        const [lo, hi] = citationRange;
        const t = hi > lo ? Math.max(0, Math.min(1, (Math.log1p(citationCount(p)) - lo) / (hi - lo))) : 0;
        return 3.5 + 7.5 * t ** 1.6;
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
    /** Counts the selections, a late answer for an earlier one is dropped */
    let edgeRequest = 0;

    /** Papers that may carry a title, most important first */
    function candidates() {
        const list = [...nodes.values()]
            .filter(
                (p) =>
                    graph?.hasNode(p.entry_id) &&
                    !hiddenByYear(p) &&
                    (!highlightSet || highlightSet.has(p.entry_id)),
            )
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
            // a stage without size (hidden, or a window dragged very small) is no error
            allowInvalidContainer: true,
            renderEdgeLabels: false,
            defaultEdgeType: "arrow",
            zIndex: true,
            stagePadding: 48,
            minCameraRatio: 0.02,
            maxCameraRatio: 6,
            nodeReducer: (node, attrs) => {
                if (node !== selectedId && hiddenByYear(nodes.get(node))) return { ...attrs, hidden: true };
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
        // not tracked, like the titles: placing stars must not rebuild the map
        r.on("afterRender", () => untrack(updateStars));

        // titles are placed after a render and again whenever the camera moved
        let regionBoxes: Box[] = [];
        const placer = createLabelPlacer(r, 30, () => [...overlayBoxes(el), ...regionBoxes]);
        let needsLabels = true;
        r.getCamera().on("updated", () => (needsLabels = true));

        // once the view rests after zooming in, the papers in view get their own names
        let rest: ReturnType<typeof setTimeout> | undefined;
        const nameView = () => {
            let next: Region[] | null = null;
            if (r.getCamera().ratio < ZOOM_NAMES_BELOW) {
                const { width: w, height: h } = r.getDimensions();
                const inView = list.filter((p) => {
                    if ((p.x === 0 && p.y === 0) || hiddenByYear(p)) return false;
                    const v = r.graphToViewport(p);
                    return v.x >= 0 && v.y >= 0 && v.x <= w && v.y <= h;
                });
                // nearly everything in view: the names of the whole map still fit
                next = inView.length > list.length * 0.85 ? null : findRegions(inView);
            }
            if (next === null && zoomRegions === null) return;
            zoomRegions = next;
            relabel();
        };
        r.getCamera().on("updated", () => {
            clearTimeout(rest);
            rest = setTimeout(nameView, 250);
        });
        r.on("afterRender", () => {
            if (!needsLabels) return;
            needsLabels = false;
            // not tracked: the names changing must not rebuild the map
            untrack(() => {
                regionBoxes = placeRegions(r, overlayBoxes(el));
                // only a few titles, the others show when hovering a point or zooming in; fewer still under the region names
                labels = placer.place(candidates(), regionBoxes.length ? 8 : 14);
            });
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
            clearTimeout(rest);
            zoomRegions = null;
            labels = [];
            stars = [];
            regionLabels = [];
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
        const request = ++edgeRequest;
        if (paper) {
            const id = paper.entry_id;
            if (!graph.hasNode(id) && !(paper.x === 0 && paper.y === 0)) {
                graph.addNode(id, nodeAttributes(paper));
                nodes.set(id, paper);
                injectedIds.push(id);
            }
            // the points on the map carry no citation lists, they are loaded for the selected paper
            loadNeighbourhood(id)
                .then((n) => {
                    if (request !== edgeRequest || !graph?.hasNode(id)) return;
                    // many links are drawn as thin plain lines, arrow heads would only add clutter
                    const many = n.cites.length + n.citedBy.length > 60;
                    const edge = {
                        type: many ? "line" : "arrow",
                        size: many ? 0.6 : 1.2,
                        color: token("--map-edge", "rgba(0,0,0,0.3)"),
                    };
                    for (const p of n.cites) {
                        if (graph.hasNode(p.entry_id) && !graph.hasEdge(id, p.entry_id)) {
                            graph.addEdge(id, p.entry_id, edge);
                            neighbours.add(p.entry_id);
                        }
                    }
                    for (const p of n.citedBy) {
                        if (graph.hasNode(p.entry_id) && !graph.hasEdge(p.entry_id, id)) {
                            graph.addEdge(p.entry_id, id, edge);
                            neighbours.add(p.entry_id);
                        }
                    }
                    relabel();
                })
                .catch(() => {});
        }
        relabel();
        updateRing();
    }

    /** Places the stars of the saved papers that are on the map and in view */
    function updateStars() {
        const r = renderer;
        const g = graph;
        if (!r || !g || !savedIds.length) {
            if (stars.length) stars = [];
            return;
        }
        const { width: w, height: h } = r.getDimensions();
        const next = [];
        for (const id of savedIds) {
            if (!g.hasNode(id)) continue;
            const d = r.getNodeDisplayData(id);
            if (!d || d.hidden) continue;
            const v = r.framedGraphToViewport(d);
            if (v.x < 0 || v.y < 0 || v.x > w || v.y > h) continue;
            const size = r.scaleSize(d.size);
            next.push({ id, x: v.x + size * 0.7, y: v.y - size * 0.7 });
        }
        stars = next;
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
        void showRegions;
        relabel();
    });
    $effect(() => {
        hideAfter = untilYear;
        relabel();
    });
    $effect(() => {
        savedIds = saved;
        renderer?.refresh({ skipIndexation: true });
    });
    // switching the colouring repaints the points and keeps the view
    $effect(() => {
        const s = scheme;
        if (!graph) return;
        for (const [id, p] of nodes) if (graph.hasNode(id)) graph.setNodeAttribute(id, "color", nodeColor(p, s));
    });
    $effect(() => {
        void selected;
        applySelection();
    });

    const camera = () => renderer?.getCamera();

    /** What the map shows right now, for the export (lib/exportMap.ts). null before the map is drawn. */
    export function scene(title: string): MapScene | null {
        const r = renderer;
        const g = graph;
        if (!r || !g) return null;
        const { width: w, height: h } = r.getDimensions();
        const at = new Map<string, { x: number; y: number; r: number; color: string; z: number }>();
        g.forEachNode((id) => {
            const d = r.getNodeDisplayData(id);
            if (!d || d.hidden) return;
            const v = r.framedGraphToViewport(d);
            at.set(id, { x: v.x, y: v.y, r: r.scaleSize(d.size), color: d.color, z: d.zIndex ?? 0 });
        });
        const lines: MapScene["lines"] = [];
        g.forEachEdge((_edge, _attrs, source, target) => {
            const a = at.get(source);
            const b = at.get(target);
            if (a && b) lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });
        });
        return {
            width: Math.round(w),
            height: Math.round(h),
            title,
            // points outside the view are left out, the ones in front are drawn last
            points: [...at.values()]
                .filter((p) => p.x > -p.r && p.y > -p.r && p.x < w + p.r && p.y < h + p.r)
                .sort((a, b) => a.z - b.z),
            lines,
            titles: labels.map((l) => ({ x: l.x, y: l.y, text: l.label, bold: l.id === selected?.entry_id })),
            names: regionLabels.map((l) => ({ x: l.x, y: l.y, text: l.label })),
            ring: ring ? { x: ring.x, y: ring.y, r: ring.size / 2 } : null,
            legend: scheme.legend.map((item) => ({
                color: resolveColor(item.color),
                label: [item.name, item.detail, item.count.toLocaleString("en")].filter(Boolean).join(" "),
            })),
            colors: {
                background: token("--surface", "#ffffff"),
                text: token("--text", "#191c26"),
                muted: token("--text-2", "#464b5a"),
                line: token("--map-edge", "#b3b7c4"),
            },
        };
    }
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

    {#each regionLabels as item (item.id)}
        <span class="region-label" style:left="{item.x}px" style:top="{item.y}px">{item.label}</span>
    {/each}

    {#each stars as star (star.id)}
        <span class="star" aria-hidden="true" style:left="{star.x}px" style:top="{star.y}px">★</span>
    {/each}

    {#if untilYear}
        <div class="year-now" aria-live="polite">up to {untilYear}</div>
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
        <span class="hint">near = similar · size = citations{stars.length ? " · ★ = in your library" : ""}</span>
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
    .star {
        position: absolute;
        transform: translate(-50%, -50%);
        color: var(--text);
        font-size: 13px;
        line-height: 1;
        -webkit-text-stroke: 3px var(--map-label-halo);
        paint-order: stroke fill;
        pointer-events: none;
    }
    .year-now {
        position: absolute;
        top: 12px;
        left: 16px;
        color: var(--text-2);
        font-size: var(--text-xl);
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        pointer-events: none;
    }
    .legend em {
        color: var(--text-3);
        font-style: normal;
    }
    .legend .hint {
        color: var(--text-3);
    }
    /* little room: the legend keeps to the colours */
    @media (max-width: 1180px) {
        .legend .hint {
            display: none;
        }
    }
</style>
