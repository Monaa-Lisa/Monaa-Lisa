<!--
  GraphLayout.svelte

  The app shell. It owns the navigation state and decides which view is shown:
    1. top     - top-level subject clusters (Physics, CS, Math, ...)
    2. sub     - subcategory clusters inside one subject
    3. papers  - the paper map of one subcategory (Graph.svelte)
    4. detail  - one paper with its citations and references (PaperDetailGraph.svelte)
  Navigation goes forward through these levels, the breadcrumbs go back.
-->
<script lang="ts">
    import ClusterGraph from "./ClusterGraph.svelte";
    import Graph from "./Graph.svelte";
    import PaperDetailGraph from "./PaperDetailGraph.svelte";
    import LoadingSpinner from "./LoadingSpinner.svelte";
    import Sidebar from "./Sidebar.svelte";
    import PaperSidebar from "./PaperSidebar.svelte";
    import Dashboard from "./Dashboard.svelte";
    import TopBar, { type Crumb } from "$lib/components/TopBar.svelte";
    import AboutDialog from "$lib/components/AboutDialog.svelte";
    import LargeLimitDialog from "$lib/components/LargeLimitDialog.svelte";
    import FavoriteDialog from "$lib/components/FavoriteDialog.svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import { Bookmark, Info, PanelRight } from "@lucide/svelte";
    import type { Paper, ViewState } from "$lib/types/paper";
    import { API_BASE_URL, MAX_PAPERS_PER_REQUEST, getPaper, getPapers } from "$lib/api";
    import { toPaper, toPapers } from "$lib/paper";
    import {
        CATEGORY_COLORS,
        CATEGORY_PREFIX,
        DEFAULT_CATEGORY_COLOR,
        paperContext,
        subClusters,
        topClusterIdByName,
        topClusters,
    } from "$lib/categories";

    // ─── limits ───────────────────────────────────────────────────────
    // 0 means "all" (still capped by the backend at MAX_PAPERS_PER_REQUEST)
    const LIMIT_OPTIONS = [100, 500, 1000, 2500, 5000, 10000, 0];
    // From this size on the user has to confirm, large maps can freeze the tab
    const LARGE_LIMIT = 10000;
    const SIDEBAR_SAMPLE = 50; // papers listed in the panel on the cluster levels

    let paperLimit = $state(1000);
    let nodeLimit = $state(1000);
    let pendingLimit = $state<{ target: "paper" | "node"; value: number } | null>(null);

    function isLarge(value: number) {
        return value === 0 || value >= LARGE_LIMIT;
    }

    function requestLimit(target: "paper" | "node", value: number) {
        if (isLarge(value)) {
            pendingLimit = { target, value };
        } else {
            applyLimit(target, value);
        }
    }

    function applyLimit(target: "paper" | "node", value: number) {
        if (target === "paper") {
            paperLimit = value;
            if (view.level === "papers") loadPapers(view.categoryId);
        } else {
            nodeLimit = value;
        }
    }

    // ─── navigation state ─────────────────────────────────────────────
    let view = $state<ViewState>({ level: "top" });
    /** Where "back" in the detail view returns to */
    let previousView: ViewState = { level: "top" };

    let papers = $state<Paper[]>([]);
    let samplePapers = $state<Paper[]>([]); // panel list on the cluster levels
    let loading = $state(false);
    let error = $state<string | null>(null);

    let panelOpen = $state(false);
    let aboutOpen = $state(false);
    let libraryOpen = $state(false);

    let authorHighlight = $state("");
    /** Latest search results of the panel, highlighted on the paper map */
    let searchHighlightPapers = $state<Paper[]>([]);
    // colour of the selected top-level category, used for its sub level and paper map
    let categoryColor = $state(DEFAULT_CATEGORY_COLOR);

    function clearHighlights() {
        authorHighlight = "";
        searchHighlightPapers = [];
    }

    function goTop() {
        view = { level: "top" };
        papers = [];
        error = null;
        clearHighlights();
    }

    function goSub(parentId: string, parentName: string) {
        view = { level: "sub", parentId, parentName };
        papers = [];
        error = null;
        clearHighlights();
        loadSamplePapers(parentId);
    }

    function goPapers(categoryId: string, categoryName: string, parentName: string) {
        view = { level: "papers", categoryId, categoryName, parentName };
        clearHighlights();
        loadPapers(categoryId);
    }

    /** Opens the detail view of a paper, remembering where we came from. */
    function openPaper(paper: Paper) {
        if (view.level !== "detail") previousView = $state.snapshot(view) as ViewState;
        const context = paperContext(paper.categories);
        const current = view.level === "papers" || view.level === "detail" ? view : null;
        view = {
            level: "detail",
            paper,
            categoryId: context.categoryId || current?.categoryId || "",
            categoryName: context.categoryName || current?.categoryName || "",
            parentName: context.parentName || current?.parentName || "",
        };
        clearHighlights();
        dashboard?.addToHistory(paper);
    }

    function closePaper() {
        clearHighlights();
        view = previousView;
    }

    /** Papers from the library only carry a few fields, load the full paper first. */
    async function openPaperById(entryId: string) {
        try {
            const paper = toPaper(await getPaper(entryId));
            if (paper) openPaper(paper);
        } catch {
            error = "This paper could not be loaded.";
        }
    }

    // ─── transitions between levels ───────────────────────────────────
    let fading = $state(false);

    /** Fades the map out, switches the view, and fades it back in. */
    function withFade(change: () => void) {
        fading = true;
        setTimeout(() => {
            change();
            requestAnimationFrame(() => (fading = false));
        }, 160);
    }

    function onTopClusterClick(e: CustomEvent<{ id: string; name: string; color: string }>) {
        withFade(() => {
            categoryColor = e.detail.color;
            goSub(e.detail.id, e.detail.name);
        });
    }

    function onSubClusterClick(e: CustomEvent<{ id: string; name: string; color: string }>) {
        if (view.level !== "sub") return;
        const parentName = view.parentName;
        withFade(() => {
            categoryColor = e.detail.color;
            goPapers(e.detail.id, e.detail.name, parentName);
        });
    }

    // ─── data loading ─────────────────────────────────────────────────
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
            samplePapers = papers;
            if (!papers.length) error = "No papers found in this category yet.";
        } catch {
            error = "The papers could not be loaded. Is the backend running?";
        } finally {
            loading = false;
        }
    }

    async function loadSamplePapers(parentId?: string) {
        try {
            const page = await getPapers({
                categories: parentId ? CATEGORY_PREFIX[parentId] : undefined,
                sort: "citations",
                take: SIDEBAR_SAMPLE,
            });
            samplePapers = toPapers(page.items);
        } catch {
            samplePapers = [];
        }
    }

    // ─── breadcrumbs ──────────────────────────────────────────────────
    const crumbs = $derived.by((): Crumb[] => {
        const list: Crumb[] = [{ label: "All categories", onclick: goTop }];
        if (view.level === "top") return list;

        const parentName = view.parentName;
        if (parentName) {
            const parentId = view.level === "sub" ? view.parentId : topClusterIdByName(parentName);
            list.push({ label: parentName, onclick: parentId ? () => goSub(parentId, parentName) : undefined });
        }
        if (view.level === "papers" || view.level === "detail") {
            const { categoryId, categoryName } = view;
            if (categoryId) {
                list.push({
                    label: categoryName || categoryId,
                    onclick: () => goPapers(categoryId, categoryName, parentName),
                });
            }
        }
        if (view.level === "detail") list.push({ label: view.paper.title });
        return list;
    });

    const panelLabel = $derived.by(() => {
        if (view.level === "sub") return view.parentName;
        if (view.level === "papers") return view.categoryName;
        if (view.level === "detail") return view.categoryName || view.parentName || "Paper";
        return "arXiv";
    });

    const panelCategoryFilter = $derived.by(() => {
        if (view.level === "papers" || view.level === "detail") return view.categoryId;
        if (view.level === "sub") return CATEGORY_PREFIX[view.parentId] ?? "";
        return "";
    });

    // ─── library (favorites and history) ──────────────────────────────
    let dashboard = $state<Dashboard>();
    /** Bumped when favorites change so isFavorite() is evaluated again */
    let favoritesVersion = $state(0);
    let favoriteCandidate = $state<Paper | null>(null);

    function isFavorite(entryId: string): boolean {
        return favoritesVersion >= 0 && dashboard ? dashboard.isFavorite(entryId) : false;
    }

    function onFavorite(e: CustomEvent<Paper>) {
        const paper = e.detail;
        if (isFavorite(paper.entry_id)) {
            dashboard?.removeFavoriteById(paper.entry_id);
            favoritesVersion += 1;
        } else {
            favoriteCandidate = paper;
        }
    }

    function saveFavorite(groupIds: string[], newGroupName: string | null) {
        if (!favoriteCandidate || !dashboard) return;
        dashboard.addFavoriteWithGroups(favoriteCandidate, groupIds, newGroupName);
        favoritesVersion += 1;
        favoriteCandidate = null;
    }
</script>

<div class="app">
    <TopBar {crumbs} onhome={goTop}>
        {#snippet actions()}
            {#if view.level === "papers"}
                <label class="limit">
                    <span>Papers</span>
                    <select
                        class="field"
                        value={paperLimit}
                        onchange={(e) => requestLimit("paper", Number(e.currentTarget.value))}
                    >
                        {#each LIMIT_OPTIONS as value}
                            <option {value}>{value === 0 ? "All" : value.toLocaleString("en")}</option>
                        {/each}
                    </select>
                </label>
            {:else if view.level === "detail"}
                <label class="limit">
                    <span>Nodes</span>
                    <select
                        class="field"
                        value={nodeLimit}
                        onchange={(e) => requestLimit("node", Number(e.currentTarget.value))}
                    >
                        {#each LIMIT_OPTIONS as value}
                            <option {value}>{value === 0 ? "All" : value.toLocaleString("en")}</option>
                        {/each}
                    </select>
                </label>
            {/if}
            <span class="divider" aria-hidden="true"></span>
            <Button variant="ghost" onclick={() => (libraryOpen = true)}>
                <Bookmark /> Library
            </Button>
            <Button variant="ghost" icon label="About" onclick={() => (aboutOpen = true)}>
                <Info />
            </Button>
            <Button
                variant="ghost"
                icon
                label={panelOpen ? "Hide paper panel" : "Show paper panel"}
                pressed={panelOpen}
                onclick={() => (panelOpen = !panelOpen)}
            >
                <PanelRight />
            </Button>
        {/snippet}
    </TopBar>

    <div class="main">
        <div class="stage" class:fading>
            {#if view.level === "top"}
                <ClusterGraph clusters={topClusters} parentColor={null} on:clusterClick={onTopClusterClick} />
            {:else if view.level === "sub"}
                <ClusterGraph
                    clusters={subClusters(view.parentId)}
                    parentColor={CATEGORY_COLORS[view.parentId] ?? DEFAULT_CATEGORY_COLOR}
                    on:clusterClick={onSubClusterClick}
                />
            {:else if view.level === "papers"}
                {#if loading}
                    <div class="state">
                        <LoadingSpinner size={32} />
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
                        {authorHighlight}
                        {searchHighlightPapers}
                        apiBaseUrl={API_BASE_URL}
                        categoryId={view.categoryId}
                        on:paperSelected={(e) => withFade(() => openPaper(e.detail))}
                    />
                    <p class="map-caption">
                        {papers.length.toLocaleString("en")} papers in {view.categoryName}, most cited first
                    </p>
                {/if}
            {:else if view.level === "detail"}
                {#key `${view.paper.entry_id}_${nodeLimit}`}
                    <PaperDetailGraph
                        paper={view.paper}
                        apiBaseUrl={API_BASE_URL}
                        {nodeLimit}
                        {authorHighlight}
                        isFavoriteCheck={isFavorite}
                        on:back={closePaper}
                        on:navigate={(e) => openPaper(e.detail)}
                        on:favorite={onFavorite}
                    />
                {/key}
            {/if}
        </div>

        {#if view.level === "detail"}
            {#key view.paper.entry_id}
                <PaperSidebar
                    paper={view.paper}
                    apiBaseUrl={API_BASE_URL}
                    isOpen={panelOpen}
                    dashboardOpen={libraryOpen}
                    isFavorite={isFavorite(view.paper.entry_id)}
                    on:toggle={() => (panelOpen = !panelOpen)}
                    on:navigate={(e) => openPaper(e.detail)}
                    on:favorite={onFavorite}
                    on:authorHighlight={(e) => (authorHighlight = e.detail)}
                />
            {/key}
        {:else}
            <Sidebar
                papers={view.level === "papers" ? papers : samplePapers}
                isOpen={panelOpen}
                dashboardOpen={libraryOpen}
                selectedPaperId={null}
                categoryFilter={panelCategoryFilter}
                categoryLabel={panelLabel}
                apiBaseUrl={API_BASE_URL}
                on:toggle={() => (panelOpen = !panelOpen)}
                on:selectPaper={(e) => openPaper(e.detail)}
                on:authorHighlight={(e) => (authorHighlight = e.detail)}
                on:searchHighlight={(e) => (searchHighlightPapers = e.detail)}
            />
        {/if}
    </div>
</div>

<Dashboard
    bind:this={dashboard}
    isOpen={libraryOpen}
    on:close={() => (libraryOpen = false)}
    on:navigate={(e) => {
        libraryOpen = false;
        openPaperById(e.detail.entry_id);
    }}
/>

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
    groups={favoritesVersion >= 0 && dashboard ? dashboard.getGroups() : []}
    onsave={saveFavorite}
    oncancel={() => (favoriteCandidate = null)}
/>

<style>
    .app {
        display: flex;
        flex-direction: column;
        width: 100vw;
        height: 100vh;
        background: var(--bg);
        overflow: hidden;
    }

    .main {
        position: relative;
        display: flex;
        flex: 1;
        min-height: 0;
        overflow: hidden;
    }

    .stage {
        position: relative;
        display: flex;
        flex: 1;
        min-width: 0;
        overflow: hidden;
        background: var(--bg);
        transition: opacity 160ms var(--ease);
    }
    .stage.fading {
        opacity: 0;
    }
    .stage :global(.graph-wrapper),
    .stage :global(.cluster-canvas),
    .stage :global(.cluster-container),
    .stage :global(.detail-wrapper) {
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
        text-align: center;
    }
    .state p {
        margin: 0;
    }

    .map-caption {
        position: absolute;
        left: 16px;
        bottom: 12px;
        margin: 0;
        color: var(--text-3);
        font-size: var(--text-xs);
        pointer-events: none;
    }

    .limit {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .limit .field {
        height: 28px;
        font-size: var(--text-xs);
    }
    .divider {
        width: 1px;
        height: 20px;
        margin: 0 6px;
        background: var(--border);
    }
</style>
