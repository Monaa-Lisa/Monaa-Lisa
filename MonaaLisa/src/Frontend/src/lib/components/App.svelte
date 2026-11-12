<!--
  App.svelte: the whole application frame.

  Header with the brand and the path, a sidebar with search and browsing on
  the left, the map in the middle and, when a paper is open, its details on
  the right.

  Map levels (the `view` state):
    top     the eight arXiv subjects (packed circles)
    sub     the categories of one subject (packed circles)
    papers  the paper map of one category (UMAP positions)
  On any level a paper can be selected. The middle then shows the paper on
  its map, its citation timeline or its related papers (`stageView`).
  The location (subject, category, paper) is mirrored in the URL so a view
  can be shared.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import { afterNavigate, replaceState } from "$app/navigation";
    import { BookMarked, Info, Menu, Moon, Pause, Play, Sun } from "@lucide/svelte";
    import Sidebar from "$lib/components/Sidebar.svelte";
    import BubbleMap from "$lib/components/BubbleMap.svelte";
    import PaperMap, { type ColorBy } from "$lib/components/PaperMap.svelte";
    import CitationTimeline, { type NetworkMode } from "$lib/components/CitationTimeline.svelte";
    import PaperDetails, { type DetailsTab } from "$lib/components/PaperDetails.svelte";
    import LibraryPanel from "$lib/components/LibraryPanel.svelte";
    import Breadcrumbs, { type Crumb } from "$lib/components/Breadcrumbs.svelte";
    import AboutDialog from "$lib/components/AboutDialog.svelte";
    import LargeLimitDialog from "$lib/components/LargeLimitDialog.svelte";
    import FavoriteDialog from "$lib/components/FavoriteDialog.svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import Spinner from "$lib/components/ui/Spinner.svelte";
    import type { CategoryNode, Paper } from "$lib/types/paper";
    import logoMark from "../../assets/logo-mark.png";
    import { MAX_PAPERS_PER_REQUEST, getCategoryCounts, getPaper, getPapers, getYearRange } from "$lib/api";
    import { primaryCategory, toPaper, toPapers } from "$lib/paper";
    import type { SimilarBy } from "$lib/neighbourhood";
    import { download, papersToCsv, sceneToCanvas, sceneToSvg } from "$lib/exportMap";
    import { library } from "$lib/library.svelte";
    import { currentTheme, setTheme, type Theme } from "$lib/theme";
    import {
        CATEGORY_PREFIX,
        subjectColor,
        subcategories,
        subcategoryName,
        subjectName,
        subjectOf,
        subjectList,
        subjects,
        type DatasetCounts,
    } from "$lib/categories";

    type MapView =
        | { level: "top" }
        | { level: "sub"; parentId: string; parentName: string }
        | { level: "papers"; categoryId: string; categoryName: string; parentId: string; parentName: string };

    type StageView = "map" | NetworkMode;

    // ─── limits ───────────────────────────────────────────────────────
    // 0 means "all" (the backend still returns at most MAX_PAPERS_PER_REQUEST)
    const LIMIT_OPTIONS = [100, 500, 1000, 2500, 5000, 10000, 0];
    // papers per group (references, citations, related) in the citation views
    const NODE_LIMIT_OPTIONS = [20, 40, 100, 250, 500, 0];
    // From this size on the user has to confirm, large maps can freeze the tab
    const LARGE_LIMIT = 10000;

    let paperLimit = $state(1000);
    let colorBy = $state<ColorBy>("category");
    let showRegions = $state(true);
    /** The paper map can be limited to years of publication, 0 = no limit */
    let yearFrom = $state(0);
    let yearTo = $state(0);
    /** Years the dataset covers, newest first, for the two selects */
    let years = $state<number[]>([]);

    /** Time-lapse over the papers on the map: the year shown up to, null = not running */
    let playYear = $state<number | null>(null);
    let playTimer: ReturnType<typeof setInterval> | undefined;

    function stopPlay() {
        clearInterval(playTimer);
        playYear = null;
    }

    /** Shows the papers on the map year by year, in the order they were published */
    function togglePlay() {
        if (playYear !== null) return stopPlay();
        const present = [...new Set(papers.map((p) => new Date(p.published ?? "").getFullYear()).filter(Boolean))].sort(
            (a, b) => a - b,
        );
        if (present.length < 2) return;
        let i = 0;
        playYear = present[0];
        playTimer = setInterval(() => {
            i++;
            if (i >= present.length) stopPlay();
            else playYear = present[i];
        }, 1100);
    }

    function setYears(from: number, to: number) {
        // a range the wrong way round is turned
        [yearFrom, yearTo] = from && to && from > to ? [to, from] : [from, to];
        if (view.level === "papers") loadPapers(view.categoryId);
    }
    let nodeLimit = $state(40);
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
    /** Papers opened before the current one, for the back button */
    let trail = $state<Paper[]>([]);
    let stageView = $state<StageView>("map");
    let detailsTab = $state<DetailsTab>("abstract");
    /** How the Similar tab and view find their papers */
    let similarBy = $state<SimilarBy>("content");

    let papers = $state<Paper[]>([]);
    let papersTotal = $state(0);
    let loading = $state(false);
    let error = $state<string | null>(null);
    /** A paper from a link or the library that could not be opened, shown over the map */
    let notice = $state<string | null>(null);

    let libraryOpen = $state(false);
    /** Small screens: the sidebar is a drawer over the map, closed until asked for */
    let sidebarOpen = $state(false);
    /** Small screens: the details cover the map, this puts them aside to look at the view */
    let detailsAside = $state(false);
    /** Height of the bar above the map, it grows when its controls wrap */
    let headHeight = $state(48);
    let aboutOpen = $state(false);
    let favoriteCandidate = $state<Paper | null>(null);
    let theme = $state<Theme>("light");
    let sidebar = $state<Sidebar>();
    let paperMap = $state<PaperMap>();

    /** Saves the paper map as it is shown: a figure (SVG, PNG) or its papers (CSV) */
    function exportMap(kind: string) {
        if (view.level !== "papers") return;
        const name = `monaa-lisa-${view.categoryId}${yearFrom || yearTo ? `-${yearFrom || "start"}-${yearTo || "now"}` : ""}`;
        if (kind === "csv") {
            download(`${name}.csv`, papersToCsv(papers), "text/csv");
            return;
        }
        const scene = paperMap?.scene(`${view.categoryName} (${view.categoryId}) · ${caption} · Monaa-Lisa`);
        if (!scene) return;
        if (kind === "svg") download(`${name}.svg`, sceneToSvg(scene), "image/svg+xml");
        else sceneToCanvas(scene).toBlob((blob) => blob && download(`${name}.png`, blob), "image/png");
    }

    let highlightedAuthor = $state("");
    let authorPapers = $state<Paper[]>([]);
    let searchResults = $state<Paper[]>([]);
    /** The router is ready, the URL may be updated */
    let routerReady = $state(false);

    /** Papers per category in the dataset, null until counted (the arXiv totals are shown meanwhile) */
    let counts = $state<DatasetCounts | null>(null);
    const subjectItems = $derived(subjectList(counts));
    const countUnit = $derived(counts ? "papers in the dataset" : "papers on arXiv");

    onMount(() => {
        getCategoryCounts()
            .then((list) => {
                counts = {
                    papers: new Map(list.map((c) => [c.id, c.papers])),
                    primary: new Map(list.map((c) => [c.id, c.primary])),
                };
            })
            .catch(() => {});
        getYearRange()
            .then(({ first, last }) => {
                if (first && last) years = Array.from({ length: last - first + 1 }, (_, i) => last - i);
            })
            .catch(() => {});
        library.load();
        theme = currentTheme();
        openFromUrl();
    });
    afterNavigate(() => (routerReady = true));

    // the related tab and the related view show the same papers, keep them together
    $effect(() => {
        if (detailsTab === "related") stageView = "related";
        else if (detailsTab === "cites" || detailsTab === "citedBy") stageView = "citations";
    });

    // the map only exists at the paper level
    $effect(() => {
        if (stageView === "map" && selected && view.level !== "papers") stageView = "citations";
    });

    // papers of the highlighted author in the current category, for the map
    $effect(() => {
        const author = highlightedAuthor;
        const v = view;
        authorPapers = [];
        if (!author || v.level !== "papers") return;
        let cancelled = false;
        getPapers({ author, categories: v.categoryId, take: 50 })
            .then((page) => {
                if (cancelled) return;
                const q = author.toLowerCase();
                authorPapers = toPapers(page.items).filter((p) => p.authors.toLowerCase().includes(q));
            })
            .catch(() => {});
        return () => {
            cancelled = true;
        };
    });

    const highlight = $derived(
        searchResults.length ? searchResults : highlightedAuthor ? [...authorPapers, ...(selected ? [selected] : [])] : null,
    );

    // ─── url ──────────────────────────────────────────────────────────
    function openFromUrl() {
        const params = new URLSearchParams(location.search);
        const category = params.get("category");
        const year = (name: string) => {
            const value = Number(params.get(name));
            return Number.isInteger(value) && value > 1900 && value < 2200 ? value : 0;
        };
        yearFrom = year("from");
        yearTo = year("to");
        const subject = params.get("subject");
        if (category && subjectOf(category)) {
            const parentId = subjectOf(category);
            view = {
                level: "papers",
                categoryId: category,
                categoryName: subcategoryName(category),
                parentId,
                parentName: subjectName(parentId),
            };
            loadPapers(category);
        } else if (subject && subjects.some((s) => s.id === subject)) {
            view = { level: "sub", parentId: subject, parentName: subjectName(subject) };
        }
        const paper = params.get("paper");
        if (paper) openPaperById(paper);
    }

    $effect(() => {
        if (!routerReady) return;
        const params = new URLSearchParams();
        if (view.level === "sub") params.set("subject", view.parentId);
        if (view.level === "papers") {
            params.set("category", view.categoryId);
            if (yearFrom) params.set("from", String(yearFrom));
            if (yearTo) params.set("to", String(yearTo));
        }
        if (selected) params.set("paper", selected.entry_id);
        const search = params.toString();
        const url = `${location.pathname}${search ? `?${search}` : ""}`;
        if (url !== `${location.pathname}${location.search}`) replaceState(url, {});
    });

    // ─── navigation ───────────────────────────────────────────────────
    function showMap(next: MapView, keepSelection = false) {
        if (next.level === "papers") sidebarOpen = false;
        if (!keepSelection) {
            selected = null;
            trail = [];
        }
        highlightedAuthor = "";
        searchResults = [];
        error = null;
        view = next;
        if (next.level === "papers") loadPapers(next.categoryId);
        else papers = [];
    }

    function showSubject(subject: CategoryNode) {
        withFade(() => showMap({ level: "sub", parentId: subject.id, parentName: subject.name }));
    }

    function showCategory(category: CategoryNode) {
        if (view.level === "top") return;
        if (view.level === "papers" && view.categoryId === category.id) return;
        const { parentId, parentName } = view;
        withFade(() =>
            showMap({ level: "papers", categoryId: category.id, categoryName: category.name, parentId, parentName }),
        );
    }

    function openPaper(paper: Paper) {
        notice = null;
        detailsAside = false;
        sidebarOpen = false;
        if (selected && selected.entry_id !== paper.entry_id) trail = [...trail, selected].slice(-20);
        if (selected?.entry_id === paper.entry_id) return;
        selected = paper;
        libraryOpen = false;
        highlightedAuthor = "";
        if (view.level !== "papers" && stageView === "map") stageView = "citations";
        library.addToHistory(paper);
    }

    function goBack() {
        const previous = trail.at(-1);
        if (!previous) return;
        trail = trail.slice(0, -1);
        selected = previous;
        highlightedAuthor = "";
    }

    function closePaper() {
        selected = null;
        trail = [];
        highlightedAuthor = "";
        stageView = "map";
        detailsTab = "abstract";
    }

    async function openPaperById(entryId: string) {
        try {
            const paper = toPaper(await getPaper(entryId));
            if (paper) openPaper(paper);
        } catch {
            notice = `The paper ${entryId} is not in the dataset or could not be loaded.`;
        }
    }

    /** Shows the selected paper on the map of its primary category */
    function locateSelected() {
        if (!selected) return;
        const categoryId = primaryCategory(selected.categories);
        const parentId = subjectOf(categoryId);
        if (!categoryId || !parentId) return;
        stageView = "map";
        detailsTab = "abstract";
        if (view.level === "papers" && view.categoryId === categoryId) return;
        showMap(
            {
                level: "papers",
                categoryId,
                categoryName: subcategoryName(categoryId),
                parentId,
                parentName: subjectName(parentId),
            },
            true,
        );
    }

    // short fade between map levels so the switch does not flash
    let fading = $state(false);
    function withFade(change: () => void) {
        fading = true;
        setTimeout(() => {
            change();
            requestAnimationFrame(() => (fading = false));
        }, 120);
    }

    function onkeydown(event: KeyboardEvent) {
        if (event.defaultPrevented) return;
        const target = event.target as HTMLElement | null;
        const typing = !!target?.closest("input, select, textarea, dialog");
        if (event.key === "/" && !typing) {
            event.preventDefault();
            sidebarOpen = true;
            sidebar?.focus();
        } else if (event.key === "Escape" && !typing) {
            if (sidebarOpen) sidebarOpen = false;
            else if (libraryOpen) libraryOpen = false;
            else if (selected) closePaper();
        }
    }

    function toggleTheme() {
        theme = theme === "dark" ? "light" : "dark";
        setTheme(theme);
    }

    // ─── data ─────────────────────────────────────────────────────────
    async function loadPapers(categoryId: string) {
        stopPlay();
        loading = true;
        error = null;
        papers = [];
        try {
            const page = await getPapers({
                categories: categoryId,
                sort: "citations",
                fields: "map",
                dateFrom: yearFrom ? `${yearFrom}-01-01` : undefined,
                dateTo: yearTo ? `${yearTo}-12-31T23:59:59.999Z` : undefined,
                take: paperLimit > 0 ? paperLimit : MAX_PAPERS_PER_REQUEST,
            });
            papers = toPapers(page.items);
            papersTotal = page.total ?? papers.length;
            if (!papers.length) {
                error = yearFrom || yearTo ? "No papers in this category in these years." : "No papers in this category yet.";
            }
        } catch {
            error = "The papers could not be loaded. Is the backend running?";
        } finally {
            loading = false;
        }
    }

    // ─── derived ui ───────────────────────────────────────────────────
    const crumbs = $derived.by((): Crumb[] => {
        const list: Crumb[] = [{ label: "All subjects", onclick: () => withFade(() => showMap({ level: "top" })) }];
        const v = view;
        if (v.level !== "top") {
            list.push({
                label: v.parentName,
                onclick: () => withFade(() => showMap({ level: "sub", parentId: v.parentId, parentName: v.parentName })),
            });
        }
        if (v.level === "papers") list.push({ label: v.categoryName });
        return list;
    });

    const scope = $derived(
        view.level === "papers"
            ? { id: view.categoryId, label: view.categoryName }
            : view.level === "sub"
              ? { id: CATEGORY_PREFIX[view.parentId] ?? "", label: view.parentName }
              : { id: "", label: "all of arXiv" },
    );

    const colorOfSubject = (c: CategoryNode) => subjectColor(c.id);
    const browse = $derived.by(() => {
        const v = view;
        if (v.level === "top") return { items: subjectItems, title: "Subjects", color: colorOfSubject, up: null };
        const color = () => subjectColor(v.parentId);
        const items = subcategories(v.parentId, counts);
        const title = `Categories in ${v.parentName}`;
        if (v.level === "sub") {
            return { items, title, color, up: { label: "All subjects", onclick: () => withFade(() => showMap({ level: "top" })) } };
        }
        return {
            items,
            title,
            color,
            up: {
                label: v.parentName,
                onclick: () => withFade(() => showMap({ level: "sub", parentId: v.parentId, parentName: v.parentName })),
            },
        };
    });

    const caption = $derived.by(() => {
        if (selected && stageView !== "map") {
            return stageView === "citations" ? "References and citations by year" : "Similar papers on the map";
        }
        if (view.level === "top") return `${subjects.length} subjects · circle area = ${countUnit} · pick one to see its categories`;
        if (view.level === "sub") return `${subcategories(view.parentId).length} categories · circle area = ${countUnit} · pick one to see its papers`;
        if (loading || error) return "";
        const shown = papers.length.toLocaleString("en");
        const total = papersTotal.toLocaleString("en");
        const range =
            yearFrom && yearTo
                ? yearFrom === yearTo
                    ? ` from ${yearFrom}`
                    : ` from ${yearFrom} to ${yearTo}`
                : yearFrom
                  ? ` since ${yearFrom}`
                  : yearTo
                    ? ` up to ${yearTo}`
                    : "";
        return (papers.length < papersTotal ? `${shown} of ${total} papers` : `${shown} papers`) + range;
    });

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
    <header class="topbar">
        <span class="menu">
            <Button
                variant="ghost"
                size="sm"
                icon
                label={sidebarOpen ? "Hide search and lists" : "Show search and lists"}
                pressed={sidebarOpen}
                onclick={() => (sidebarOpen = !sidebarOpen)}
            >
                <Menu />
            </Button>
        </span>
        <button class="brand" onclick={() => withFade(() => showMap({ level: "top" }))} title="Back to all subjects">
            <img src={logoMark} alt="" width="30" height="30" />
            <span class="brand-text">
                <span class="name">Monaa-Lisa</span>
                <span class="tagline">A map of arXiv research</span>
            </span>
        </button>
        <span class="divider" aria-hidden="true"></span>
        <Breadcrumbs {crumbs} />
        <div class="actions">
            <Button variant="ghost" size="sm" pressed={libraryOpen} onclick={() => (libraryOpen = !libraryOpen)}>
                <BookMarked /> <span class="wide-only">Library</span>
                {#if library.favorites.length}<span class="badge">{library.favorites.length}</span>{/if}
            </Button>
            <Button variant="ghost" size="sm" onclick={() => (aboutOpen = true)}><Info /> <span class="wide-only">About &amp; method</span></Button>
            <Button
                variant="ghost"
                size="sm"
                icon
                label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                onclick={toggleTheme}
            >
                {#if theme === "dark"}<Sun />{:else}<Moon />{/if}
            </Button>
        </div>
    </header>

    <div
        class="columns"
        class:with-panel={selected !== null || libraryOpen}
        class:sidebar-open={sidebarOpen}
        class:details-aside={detailsAside && selected !== null && !libraryOpen}
        style:--head-height="{headHeight + 1}px"
    >
        <Sidebar
            bind:this={sidebar}
            scope={scope.id}
            scopeLabel={scope.label}
            categories={browse.items}
            categoriesTitle={browse.title}
            categoryColor={browse.color}
            categoryUnit={countUnit}
            showIds={view.level !== "top"}
            activeCategoryId={view.level === "papers" ? view.categoryId : null}
            up={browse.up}
            onbrowse={(item) => (view.level === "top" ? showSubject(item) : showCategory(item))}
            {papers}
            papersTitle="On the map, most cited first"
            selectedId={selected?.entry_id ?? null}
            onselect={openPaper}
            onresults={(found) => (searchResults = found)}
        />

        {#if sidebarOpen}
            <button class="scrim" aria-label="Hide search and lists" onclick={() => (sidebarOpen = false)}></button>
        {/if}

        {#if selected && !libraryOpen}
            <button class="peek" onclick={() => (detailsAside = !detailsAside)}>
                {detailsAside ? "Show details" : stageView === "map" ? "Show map" : "Show chart"}
            </button>
        {/if}

        <main class="stage">
            <div class="stage-head" bind:clientHeight={headHeight}>
                {#if selected}
                    <div class="segmented" role="tablist" aria-label="View">
                        {#if view.level === "papers"}
                            <button role="tab" aria-selected={stageView === "map"} class:active={stageView === "map"} onclick={() => (stageView = "map")}>Map</button>
                        {/if}
                        <button
                            role="tab"
                            aria-selected={stageView === "citations"}
                            class:active={stageView === "citations"}
                            onclick={() => (stageView = "citations")}>Citations</button
                        >
                        <button
                            role="tab"
                            aria-selected={stageView === "related"}
                            class:active={stageView === "related"}
                            onclick={() => (stageView = "related")}>Similar</button
                        >
                    </div>
                {/if}
                <!-- title and caption share what the controls leave, and shorten before the bar wraps -->
                <div class="lead">
                    {#if !selected}
                        <h1 class="stage-title">
                            {#if view.level === "top"}
                                Subjects on arXiv
                            {:else}
                                {view.level === "sub" ? view.parentName : view.categoryName}
                                {#if view.level === "papers"}<span class="ident">{view.categoryId}</span>{/if}
                            {/if}
                        </h1>
                    {/if}
                    <span class="caption">{caption}</span>
                </div>
                {#if selected && stageView !== "map"}
                    <label class="limit">
                        <span>Per group</span>
                        <select class="field" value={nodeLimit} onchange={(e) => requestLimit("node", Number(e.currentTarget.value))}>
                            {#each NODE_LIMIT_OPTIONS as value}
                                <option {value}>{value === 0 ? "All" : value.toLocaleString("en")}</option>
                            {/each}
                        </select>
                    </label>
                {:else if view.level === "papers"}
                    {#if papers.length && stageView === "map"}
                        <select
                            class="field export"
                            aria-label="Export this map"
                            title="Save this map as a figure, or its papers as a table"
                            value=""
                            onchange={(e) => {
                                exportMap(e.currentTarget.value);
                                e.currentTarget.value = "";
                            }}
                        >
                            <option value="" disabled hidden>Export</option>
                            <option value="svg">Figure, SVG (print)</option>
                            <option value="png">Figure, PNG</option>
                            <option value="csv">Papers, CSV</option>
                        </select>
                    {/if}
                    <label class="limit" title="Name the regions of the map after the terms typical for their titles">
                        <input type="checkbox" bind:checked={showRegions} />
                        <span>Topics</span>
                    </label>
                    {#if years.length}
                        <span class="limit">
                            <label for="year-from">Years</label>
                            <select
                                id="year-from"
                                class="field year"
                                value={yearFrom}
                                aria-label="From year"
                                onchange={(e) => setYears(Number(e.currentTarget.value), yearTo)}
                            >
                                <option value={0}>from</option>
                                {#each years as y}<option value={y}>{y}</option>{/each}
                            </select>
                            <select
                                class="field year"
                                value={yearTo}
                                aria-label="To year"
                                onchange={(e) => setYears(yearFrom, Number(e.currentTarget.value))}
                            >
                                <option value={0}>to</option>
                                {#each years as y}<option value={y}>{y}</option>{/each}
                            </select>
                            <button
                                class="play"
                                title={playYear === null ? "Play the years: show the papers in the order they were published" : "Stop"}
                                aria-label={playYear === null ? "Play the years" : "Stop"}
                                aria-pressed={playYear !== null}
                                onclick={togglePlay}
                            >
                                {#if playYear === null}<Play />{:else}<Pause />{/if}
                            </button>
                        </span>
                    {/if}
                    <label class="limit">
                        <select class="field" bind:value={colorBy} aria-label="Colour of the points">
                            <option value="category">Colour: category</option>
                            <option value="year">Colour: year</option>
                        </select>
                    </label>
                    <label class="limit">
                        <select class="field" value={paperLimit} aria-label="Number of papers, most cited first" onchange={(e) => requestLimit("paper", Number(e.currentTarget.value))}>
                            {#each LIMIT_OPTIONS as value}
                                <option {value}>{value === 0 ? "All papers" : `Top ${value.toLocaleString("en")}`}</option>
                            {/each}
                        </select>
                    </label>
                {/if}
            </div>

            <div class="stage-body" class:fading>
                {#if notice}
                    <p class="notice" role="status">
                        {notice}
                        <button onclick={() => (notice = null)} aria-label="Dismiss">×</button>
                    </p>
                {/if}
                {#if selected && stageView !== "map"}
                    {#key selected.entry_id}
                        <CitationTimeline
                            paper={selected}
                            mode={stageView}
                            {nodeLimit}
                            {highlightedAuthor}
                            {similarBy}
                            context={view.level === "papers" ? papers : []}
                            onselect={openPaper}
                        />
                    {/key}
                {:else if view.level === "top"}
                    <BubbleMap items={browse.items} color={browse.color} unit={countUnit} onselect={showSubject} />
                {:else if view.level === "sub"}
                    <BubbleMap items={browse.items} color={browse.color} unit={countUnit} showIds onselect={showCategory} />
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
                    <PaperMap
                        bind:this={paperMap}
                        {papers}
                        {highlight}
                        {selected}
                        {colorBy}
                        {showRegions}
                        untilYear={playYear}
                        saved={library.favorites.map((f) => f.entry_id)}
                        onselect={openPaper}
                    />
                {/if}
            </div>
        </main>

        {#if libraryOpen}
            <LibraryPanel onopen={openPaperById} onclose={() => (libraryOpen = false)} />
        {:else if selected}
            <PaperDetails
                paper={selected}
                bind:tab={detailsTab}
                bind:similarBy
                isFavorite={library.isFavorite(selected.entry_id)}
                {highlightedAuthor}
                backTo={trail.at(-1)?.title ?? null}
                onback={goBack}
                onselect={openPaper}
                onfavorite={() => selected && toggleFavorite(selected)}
                onauthor={(name) => (highlightedAuthor = name)}
                canLocate={!(
                    stageView === "map" &&
                    view.level === "papers" &&
                    view.categoryId === primaryCategory(selected.categories)
                )}
                onlocate={locateSelected}
                onclose={closePaper}
            />
        {/if}
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
        display: flex;
        flex-direction: column;
        background: var(--bg);
        overflow: hidden;
    }

    .topbar {
        display: flex;
        align-items: center;
        gap: 16px;
        height: var(--header-height);
        padding: 0 12px 0 14px;
        background: var(--header-bg);
        color: var(--header-fg);
        flex-shrink: 0;
        /* breadcrumbs and buttons read these */
        --text: var(--header-fg);
        --text-2: var(--header-fg-2);
        --text-3: var(--header-fg-2);
        --border-strong: var(--header-border);
        --surface-2: var(--header-hover);
        --accent: var(--header-fg);
    }
    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0;
        border: 0;
        background: none;
        color: inherit;
        text-align: left;
        cursor: pointer;
        flex-shrink: 0;
    }
    .brand img {
        width: 30px;
        height: 30px;
        border-radius: 6px;
        box-shadow: 0 0 0 1px var(--header-border);
    }
    .brand-text {
        display: grid;
        line-height: 1.15;
    }
    .brand .name {
        font-size: var(--text-md);
        font-weight: 600;
        letter-spacing: -0.005em;
    }
    .brand .tagline {
        color: var(--header-fg-2);
        font-size: 0.75rem;
    }
    .divider {
        width: 1px;
        height: 24px;
        background: var(--header-border);
        flex-shrink: 0;
    }
    .actions {
        display: flex;
        align-items: center;
        gap: 2px;
        margin-left: auto;
        flex-shrink: 0;
    }
    .badge {
        padding: 0 6px;
        border-radius: 8px;
        background: var(--header-fg);
        color: var(--header-bg);
        font-variant-numeric: tabular-nums;
        font-size: 11px;
        font-weight: 500;
    }

    .columns {
        display: grid;
        grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
        flex: 1;
        min-height: 0;
    }
    .columns.with-panel {
        grid-template-columns: var(--sidebar-width) minmax(0, 1fr) var(--panel-width);
    }
    /* small screens: the details lie over the right side of the map, below its toolbar */
    @media (max-width: 1180px) {
        .columns {
            position: relative;
        }
        .columns.with-panel {
            grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
        }
        .columns.with-panel > :global(aside:not(.sidebar)) {
            position: absolute;
            top: var(--head-height, 48px);
            right: 0;
            bottom: 0;
            z-index: 5;
            width: var(--overlay-width);
            box-shadow: var(--shadow-pop);
        }
        .columns.with-panel {
            --overlay-width: min(var(--panel-width), calc(100% - var(--sidebar-width) - 120px));
        }
        /* the maps lay themselves out in the uncovered part */
        .columns.with-panel .stage-body {
            padding-right: var(--overlay-width);
        }
        .columns.with-panel .state {
            right: var(--overlay-width);
        }
    }

    /* phones and narrow windows: one column, the sidebar is a drawer and the details cover the map */
    .menu,
    .scrim,
    .peek {
        display: none;
    }
    @media (max-width: 900px) {
        .menu {
            display: block;
            margin: 0 -8px 0 -6px;
        }
        .topbar {
            gap: 10px;
        }
        .brand-text,
        .divider,
        .wide-only {
            display: none;
        }
        .columns,
        .columns.with-panel {
            grid-template-columns: minmax(0, 1fr);
            --overlay-width: 100%;
        }
        .columns > :global(aside.sidebar) {
            position: absolute;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 7;
            width: min(340px, 88vw);
            box-shadow: var(--shadow-pop);
            transform: translateX(-105%);
            visibility: hidden;
            transition:
                transform 160ms var(--ease),
                visibility 160ms;
        }
        .columns.sidebar-open > :global(aside.sidebar) {
            transform: none;
            visibility: visible;
        }
        .scrim {
            display: block;
            position: absolute;
            inset: 0;
            z-index: 6;
            border: 0;
            background: rgba(10, 12, 24, 0.35);
        }
        .columns.with-panel > :global(aside:not(.sidebar)) {
            top: 0;
            width: 100%;
        }
        /* the details cover the whole map here, it keeps its size underneath */
        .columns.with-panel .stage-body {
            padding-right: 0;
        }
        .columns.with-panel .state {
            right: 0;
        }
        .topbar :global(nav) {
            min-width: 0;
            overflow: hidden;
        }
        .stage-head {
            padding: 8px 10px;
        }
        .caption {
            display: none;
        }
        .columns.details-aside > :global(aside:not(.sidebar)) {
            display: none;
        }
        /* with the details aside the button sits at the top, clear of the legend */
        .columns.details-aside .peek {
            top: calc(var(--head-height, 48px) + 10px);
            bottom: auto;
        }
        .peek {
            display: block;
            position: absolute;
            left: 50%;
            bottom: 14px;
            z-index: 8;
            padding: 8px 16px;
            border: 0;
            border-radius: 999px;
            background: var(--accent);
            box-shadow: var(--shadow-pop);
            color: var(--accent-fg);
            font-size: var(--text-sm);
            font-weight: 500;
            transform: translateX(-50%);
            cursor: pointer;
        }
    }

    .stage {
        display: flex;
        flex-direction: column;
        min-width: 0;
        min-height: 0;
    }
    .stage-head {
        display: flex;
        align-items: center;
        /* the controls move to a second row when the bar gets too narrow for them */
        flex-wrap: wrap;
        gap: 8px 12px;
        min-height: 48px;
        padding: 8px 16px 8px 18px;
        border-bottom: 1px solid var(--border);
        background: var(--surface);
        flex-shrink: 0;
    }
    .lead {
        display: flex;
        align-items: baseline;
        gap: 12px;
        flex: 1 1 0;
        min-width: 0;
        overflow: hidden;
    }
    .lead:has(.stage-title) {
        min-width: 150px;
    }
    .stage-title {
        min-width: 0;
        margin: 0;
        color: var(--text);
        font-size: var(--text-md);
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 0 1 auto;
    }
    .stage-title .ident {
        margin-left: 6px;
        color: var(--text-3);
        font-weight: 400;
    }
    .caption {
        /* gives way before the title does */
        flex: 0 100 auto;
        min-width: 0;
        color: var(--text-3);
        font-size: var(--text-sm);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .limit {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--text-3);
        font-size: var(--text-xs);
        white-space: nowrap;
    }
    .export {
        width: 78px;
        height: 26px;
        font-size: var(--text-xs);
        color: var(--text-2);
    }
    .play {
        display: grid;
        place-items: center;
        width: 26px;
        height: 26px;
        padding: 0;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        color: var(--text-2);
        cursor: pointer;
    }
    .play:hover,
    .play[aria-pressed="true"] {
        border-color: var(--border-strong);
        color: var(--text);
    }
    .play :global(svg) {
        width: 13px;
        height: 13px;
    }
    .limit .year {
        width: 70px;
    }
    .limit .field {
        height: 26px;
        font-size: var(--text-xs);
    }

    .stage-body {
        position: relative;
        flex: 1;
        min-height: 0;
        transition: opacity 120ms var(--ease);
    }
    .stage-body.fading {
        opacity: 0;
    }

    .state {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        color: var(--text-2);
    }
    .state p {
        margin: 0;
    }
    .notice {
        position: absolute;
        top: 12px;
        left: 50%;
        z-index: 4;
        display: flex;
        align-items: center;
        gap: 10px;
        max-width: calc(100% - 32px);
        margin: 0;
        padding: 6px 8px 6px 12px;
        border: 1px solid var(--border-strong);
        border-radius: var(--radius);
        background: var(--surface);
        box-shadow: var(--shadow-pop);
        color: var(--text);
        font-size: var(--text-sm);
        transform: translateX(-50%);
    }
    .notice button {
        padding: 0 6px;
        border: 0;
        background: none;
        color: var(--text-3);
        font-size: 18px;
        line-height: 1;
        cursor: pointer;
    }
</style>
