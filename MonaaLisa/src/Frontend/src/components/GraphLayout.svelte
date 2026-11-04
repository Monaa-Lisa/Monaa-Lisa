<!--
  GraphLayout.svelte

  The whole app. The map fills the window and the controls float above it.

  Map levels (the `view` state):
    top     top-level subjects (Physics, Computer Science, ...)
    sub     subcategories of one subject
    papers  the paper map of one subcategory (UMAP positions)
  On top of any level a paper can be selected (`selected`). Then the middle
  shows its citation network or related papers, and the inspector on the
  right shows its details. Closing it goes back to the map.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import ClusterGraph from "./ClusterGraph.svelte";
    import Graph from "./Graph.svelte";
    import SearchPanel from "$lib/components/SearchPanel.svelte";
    import Breadcrumbs, { type Crumb } from "$lib/components/Breadcrumbs.svelte";
    import Inspector, { type InspectorTab } from "$lib/components/Inspector.svelte";
    import CitationNetwork, { type NetworkMode } from "$lib/components/CitationNetwork.svelte";
    import LibraryPanel from "$lib/components/LibraryPanel.svelte";
    import AboutDialog from "$lib/components/AboutDialog.svelte";
    import LargeLimitDialog from "$lib/components/LargeLimitDialog.svelte";
    import FavoriteDialog from "$lib/components/FavoriteDialog.svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import Spinner from "$lib/components/ui/Spinner.svelte";
    import { Bookmark, Info } from "@lucide/svelte";
    import type { Paper } from "$lib/types/paper";
    import { API_BASE_URL, MAX_PAPERS_PER_REQUEST, getPaper, getPapers } from "$lib/api";
    import { toPaper, toPapers } from "$lib/paper";
    import { library } from "$lib/library.svelte";
    import {
        CATEGORY_COLORS,
        CATEGORY_PREFIX,
        DEFAULT_CATEGORY_COLOR,
        subClusters,
        topClusters,
    } from "$lib/categories";

    type MapView =
        | { level: "top" }
        | { level: "sub"; parentId: string; parentName: string }
        | { level: "papers"; categoryId: string; categoryName: string; parentId: string; parentName: string };

    // ─── limits ───────────────────────────────────────────────────────
    // 0 means "all" (the backend still returns at most MAX_PAPERS_PER_REQUEST)
    const LIMIT_OPTIONS = [100, 500, 1000, 2500, 5000, 10000, 0];
    // From this size on the user has to confirm, large maps can freeze the tab
    const LARGE_LIMIT = 10000;
    const TOP_PAPERS = 50; // listed in the search card when nothing is searched

    let paperLimit = $state(1000);
    let nodeLimit = $state(500);
    let pendingLimit = $state<{ target: "paper" | "node"; value: number } | null>(null);

    function requestLimit(target: "paper" | "node", value: number) {
        if (value === 0 || value >= LARGE_LIMIT) pendingLimit = { target, value };
        else applyLimit(target, value);
    }

    function applyLimit(target: "paper" | "node", value: number) {
        if (target === "node") {
            nodeLimit = value;
            return;
        }
        paperLimit = value;
        if (view.level === "papers") loadPapers(view.categoryId);
    }

    // ─── state ────────────────────────────────────────────────────────
    let view = $state<MapView>({ level: "top" });
    let selected = $state<Paper | null>(null);
    let inspectorTab = $state<InspectorTab>("overview");
    let networkMode = $state<NetworkMode>("citations");

    let papers = $state<Paper[]>([]);
    let topPapers = $state<Paper[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);

    let libraryOpen = $state(false);
    let listOpen = $state(false);
    let aboutOpen = $state(false);
    let favoriteCandidate = $state<Paper | null>(null);

    let highlightedAuthor = $state("");
    let searchResults = $state<Paper[]>([]);
    let categoryColor = $state(DEFAULT_CATEGORY_COLOR);

    onMount(() => {
        library.load();
        loadTopPapers();
    });

    // the related tab and the related network show the same papers, keep them together
    $effect(() => {
        if (inspectorTab === "related") networkMode = "related";
        else if (inspectorTab === "cites" || inspectorTab === "citedBy") networkMode = "citations";
    });

    // ─── navigation ───────────────────────────────────────────────────
    function showMap(next: MapView) {
        selected = null;
        highlightedAuthor = "";
        searchResults = [];
        error = null;
        view = next;
        if (next.level === "papers") loadPapers(next.categoryId);
        else loadTopPapers(next.level === "sub" ? next.parentId : undefined);
    }

    function openPaper(paper: Paper) {
        selected = paper;
        listOpen = false;
        highlightedAuthor = "";
        libraryOpen = false;
        library.addToHistory(paper);
    }

    function closePaper() {
        selected = null;
        highlightedAuthor = "";
    }

    async function openPaperById(entryId: string) {
        try {
            const paper = toPaper(await getPaper(entryId));
            if (paper) openPaper(paper);
        } catch {
            error = "This paper could not be loaded.";
        }
    }

    // short fade between map levels so the switch does not flash
    let fading = $state(false);
    function withFade(change: () => void) {
        fading = true;
        setTimeout(() => {
            change();
            requestAnimationFrame(() => (fading = false));
        }, 150);
    }

    function onTopClusterClick(e: CustomEvent<{ id: string; name: string; color: string }>) {
        withFade(() => {
            categoryColor = e.detail.color;
            showMap({ level: "sub", parentId: e.detail.id, parentName: e.detail.name });
        });
    }

    function onSubClusterClick(e: CustomEvent<{ id: string; name: string; color: string }>) {
        if (view.level !== "sub") return;
        const { parentId, parentName } = view;
        withFade(() => {
            categoryColor = e.detail.color;
            showMap({ level: "papers", categoryId: e.detail.id, categoryName: e.detail.name, parentId, parentName });
        });
    }

    function onkeydown(event: KeyboardEvent) {
        if (event.key !== "Escape" || event.defaultPrevented) return;
        if ((event.target as HTMLElement)?.closest("input, select, textarea, dialog")) return;
        if (libraryOpen) libraryOpen = false;
        else if (selected) closePaper();
    }

    // ─── data ─────────────────────────────────────────────────────────
    async function loadPapers(categoryId: string) {
        loading = true;
        error = null;
        papers = [];
        try {
            const page = await getPapers({
                categories: categoryId,
                sort: "citations",
                take: paperLimit > 0 ? paperLimit : MAX_PAPERS_PER_REQUEST,
            });
            papers = toPapers(page.items);
            topPapers = papers.slice(0, TOP_PAPERS);
            if (!papers.length) error = "No papers in this category yet.";
        } catch {
            error = "The papers could not be loaded. Is the backend running?";
        } finally {
            loading = false;
        }
    }

    async function loadTopPapers(parentId?: string) {
        try {
            const page = await getPapers({
                categories: parentId ? CATEGORY_PREFIX[parentId] : undefined,
                sort: "citations",
                take: TOP_PAPERS,
            });
            topPapers = toPapers(page.items);
        } catch {
            topPapers = [];
        }
    }

    // ─── derived ui ───────────────────────────────────────────────────
    const crumbsList = $derived.by((): Crumb[] => {
        const list: Crumb[] = [{ label: "All subjects", onclick: () => showMap({ level: "top" }) }];
        const v = view;
        if (v.level !== "top") {
            list.push({
                label: v.parentName,
                onclick: () => showMap({ level: "sub", parentId: v.parentId, parentName: v.parentName }),
            });
        }
        if (v.level === "papers") list.push({ label: v.categoryName, onclick: closePaper });
        if (selected) list.push({ label: selected.title });
        return list;
    });

    const scope = $derived(
        view.level === "papers"
            ? { id: view.categoryId, label: view.categoryName }
            : view.level === "sub"
              ? { id: CATEGORY_PREFIX[view.parentId] ?? "", label: view.parentName }
              : { id: "", label: "all papers" },
    );

    function saveFavorite(groupId: string | null, newGroupName: string | null) {
        if (!favoriteCandidate) return;
        library.addFavorite(favoriteCandidate, groupId ? [groupId] : [], newGroupName);
        favoriteCandidate = null;
    }

    function toggleFavorite(paper: Paper) {
        if (library.isFavorite(paper.entry_id)) library.removeFavorite(paper.entry_id);
        else favoriteCandidate = paper;
    }
</script>

<svelte:window {onkeydown} />

<div class="app">
    <main class="stage" class:fading class:beside-panel={selected !== null || libraryOpen}>
        {#if selected}
            {#key selected.entry_id}
                <CitationNetwork
                    paper={selected}
                    mode={networkMode}
                    {nodeLimit}
                    {highlightedAuthor}
                    onselect={openPaper}
                />
            {/key}
        {:else if view.level === "top"}
            <ClusterGraph clusters={topClusters} parentColor={null} on:clusterClick={onTopClusterClick} />
        {:else if view.level === "sub"}
            <ClusterGraph
                clusters={subClusters(view.parentId)}
                parentColor={CATEGORY_COLORS[view.parentId] ?? DEFAULT_CATEGORY_COLOR}
                on:clusterClick={onSubClusterClick}
            />
        {:else if loading}
            <div class="state">
                <Spinner size={24} />
                <p>Loading papers in {view.categoryName}</p>
            </div>
        {:else if error}
            <div class="state">
                <p>{error}</p>
                <Button onclick={() => view.level === "papers" && loadPapers(view.categoryId)}>Try again</Button>
            </div>
        {:else}
            <Graph
                {papers}
                selectedPaperId={null}
                {categoryColor}
                authorHighlight={highlightedAuthor}
                searchHighlightPapers={searchResults}
                apiBaseUrl={API_BASE_URL}
                categoryId={view.categoryId}
                on:paperSelected={(e) => openPaper(e.detail)}
            />
            <p class="caption">
                {papers.length.toLocaleString("en")} papers in {view.categoryName} · placed by topic similarity
            </p>
        {/if}
    </main>

    <div class="overlay">
        <div class="top-left">
            <SearchPanel
                scope={scope.id}
                scopeLabel={scope.label}
                {topPapers}
                onselect={openPaper}
                onresults={(found) => (searchResults = found)}
                onhome={() => showMap({ level: "top" })}
                bind:listOpen
            >
                {#snippet crumbs()}<Breadcrumbs crumbs={crumbsList} />{/snippet}
            </SearchPanel>
        </div>

        {#if selected}
            <div class="top-center card segmented" role="tablist" aria-label="Network view">
                <button
                    role="tab"
                    aria-selected={networkMode === "citations"}
                    class:active={networkMode === "citations"}
                    onclick={() => (networkMode = "citations")}>Citations</button
                >
                <button
                    role="tab"
                    aria-selected={networkMode === "related"}
                    class:active={networkMode === "related"}
                    onclick={() => (networkMode = "related")}>Related</button
                >
            </div>
        {/if}

        <div class="right">
            <div class="toolbar card">
                {#if selected}
                    <label class="limit">
                        <span>Nodes</span>
                        <select class="field" value={nodeLimit} onchange={(e) => requestLimit("node", Number(e.currentTarget.value))}>
                            {#each LIMIT_OPTIONS as value}
                                <option {value}>{value === 0 ? "All" : value.toLocaleString("en")}</option>
                            {/each}
                        </select>
                    </label>
                {:else if view.level === "papers"}
                    <label class="limit">
                        <span>Papers</span>
                        <select class="field" value={paperLimit} onchange={(e) => requestLimit("paper", Number(e.currentTarget.value))}>
                            {#each LIMIT_OPTIONS as value}
                                <option {value}>{value === 0 ? "All" : value.toLocaleString("en")}</option>
                            {/each}
                        </select>
                    </label>
                {/if}
                <Button variant="ghost" size="sm" pressed={libraryOpen} onclick={() => (libraryOpen = !libraryOpen)}>
                    <Bookmark /> Library
                </Button>
                <Button variant="ghost" size="sm" icon label="About Monaa-Lisa" onclick={() => (aboutOpen = true)}>
                    <Info />
                </Button>
            </div>

            {#if libraryOpen}
                <LibraryPanel onopen={openPaperById} onclose={() => (libraryOpen = false)} />
            {:else if selected}
                <Inspector
                    paper={selected}
                    bind:tab={inspectorTab}
                    isFavorite={library.isFavorite(selected.entry_id)}
                    {highlightedAuthor}
                    onselect={openPaper}
                    onfavorite={() => selected && toggleFavorite(selected)}
                    onauthor={(name) => (highlightedAuthor = name)}
                    onclose={closePaper}
                />
            {/if}
        </div>
    </div>
</div>

<AboutDialog open={aboutOpen} onclose={() => (aboutOpen = false)} />

<LargeLimitDialog
    limit={pendingLimit?.value ?? null}
    oncancel={() => (pendingLimit = null)}
    onconfirm={() => {
        if (pendingLimit) applyLimit(pendingLimit.target, pendingLimit.value);
        pendingLimit = null;
    }}
/>

<FavoriteDialog
    paper={favoriteCandidate}
    groups={library.groups}
    onsave={saveFavorite}
    oncancel={() => (favoriteCandidate = null)}
/>

<style>
    .app {
        position: fixed;
        inset: 0;
        background: var(--bg);
        overflow: hidden;
    }

    .stage {
        position: absolute;
        inset: 0;
        display: flex;
        transition: opacity 150ms var(--ease);
    }
    .stage.fading {
        opacity: 0;
    }
    /* the network moves left so the inspector does not cover it */
    .stage.beside-panel:has(:global(.network)) {
        right: calc(var(--panel-width) + 24px);
    }
    .stage :global(.graph-wrapper),
    .stage :global(.cluster-container) {
        width: 100% !important;
        height: 100% !important;
    }

    .state {
        margin: auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 16px;
        color: var(--text-2);
    }
    .state p {
        margin: 0;
    }
    .caption {
        position: absolute;
        left: 16px;
        bottom: 14px;
        margin: 0;
        color: var(--text-3);
        font-size: var(--text-xs);
        pointer-events: none;
    }

    /* floating ui, the overlay itself lets clicks through to the map */
    .overlay {
        position: absolute;
        inset: 12px;
        pointer-events: none;
    }
    .overlay > * {
        pointer-events: auto;
    }
    .top-left {
        position: absolute;
        top: 0;
        left: 0;
        max-height: 100%;
        display: flex;
    }
    .top-center {
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
    }
    .right {
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 8px;
        pointer-events: none;
    }
    .right > :global(*) {
        pointer-events: auto;
    }
    .right > :global(aside) {
        min-height: 0;
    }

    .toolbar {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px;
    }
    .limit {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 0 4px 0 8px;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .limit .field {
        height: 28px;
        font-size: var(--text-xs);
    }

    .segmented {
        display: flex;
        padding: 3px;
        gap: 2px;
    }
    .segmented button {
        padding: 5px 14px;
        border: 0;
        border-radius: var(--radius);
        background: none;
        color: var(--text-3);
        font-size: var(--text-sm);
        font-weight: 500;
        cursor: pointer;
    }
    .segmented button:hover {
        color: var(--text);
    }
    .segmented button.active {
        background: var(--surface-3);
        color: var(--text);
    }
</style>
