<!--
  Sidebar.svelte

  Slide-in paper list that appears on the right side of the screen.
  Used in both the papers view (Graph.svelte) and the detail view (PaperDetailGraph.svelte).

  Supports:
    - Free-text search (debounced, hits /papers?search=...)
    - Advanced filter panel: title, author, abstract, date range, sort order
    - Filter badges: shown after clicking Search so the user knows what's active
    - Author highlight: dispatches 'authorHighlight' event so the graph can
      highlight/add nodes whose authors match the search term
-->
<script lang="ts">
    import { createEventDispatcher, tick } from "svelte";
    import { env as publicEnv } from "$env/dynamic/public";
    import type { Paper } from "$lib/types/paper";
    import { getClusterColor } from "../utils/clusterColors";
    import { getSubcategoryName } from "../utils/arxivTaxonomy";

    export let papers: Paper[] = [];
    export let isOpen: boolean = false;
    export let selectedPaperId: string | null = null;
    /** When true (dashboard is open), the toggle button is blurred and non-interactive. */
    export let dashboardOpen: boolean = false;
    /** When true, citations/references can be expanded (paper-detail view only) */
    export let allowExpand: boolean = false;
    /** Category ID prefix used to scope backend search, e.g. "cs.AI" */
    export let categoryFilter: string = "";
    /** Human-readable label shown in the sidebar header, e.g. "Computer Science" */
    export let categoryLabel: string = "ArXiv";
    /** Backend API base URL */
    export let apiBaseUrl: string =
        publicEnv.PUBLIC_API_BASE_URL || "http://localhost:3000/";

    const dispatch = createEventDispatcher<{
        toggle: void;
        selectPaper: Paper;
        authorHighlight: string;
        /** Fired whenever the search results change; carries the full paper objects so
         *  the graph can highlight matching nodes and add any that are missing. */
        searchHighlight: Paper[];
    }>();

    let currentNeighbourIds: string[] = []; // Alle IDs, die wir filtern wollen (Nachbarn)

    // Wir beobachten Änderungen an localSelected, um die Nachbar-IDs zu aktualisieren
    $: if (localSelected && allowExpand) {
        currentNeighbourIds = [
            ...(localSelected.citations || []),
            ...(localSelected.references || []),
        ];
    } else {
        currentNeighbourIds = [];
    }

    // ─── backend search state ─────────────────────────────────────────
    let searchResults: Paper[] | null = null;
    let searchLoading = false;
    let searchError: string | null = null;
    let searchTotal = 0;

    // Advanced filter form type - each field maps to a backend query param
    const TODAY = new Date().toISOString().slice(0, 10);
    interface AdvFilter {
        titleQuery: string; // search by paper title
        dateFrom: string; // published after this date
        dateTo: string; // published before this date
        authorQuery: string; // search by author name
        abstractQuery: string; // search for text in abstract
        /** Sort order: published_desc = newest first, published_asc = oldest first, citations = most cited first */
        sort: "published_desc" | "published_asc" | "citations";
    }
    // Default sort: newest papers first
    let adv: AdvFilter = {
        titleQuery: "",
        dateFrom: "",
        dateTo: "",
        authorQuery: "",
        abstractQuery: "",
        sort: "published_desc",
    };
    let advError: string | null = null;
    let advancedOpen = false;

    // ─── filter badges ──────────────────────────────────────────────
    interface FilterBadge {
        key: string;
        label: string;
    }
    let filterBadges: FilterBadge[] = [];

    function buildBadges() {
        const badges: FilterBadge[] = [];
        if (query.trim())
            badges.push({ key: "query", label: `"${query.trim()}"` });
        if (adv.titleQuery.trim())
            badges.push({
                key: "title",
                label: `Title: ${adv.titleQuery.trim()}`,
            });
        if (adv.authorQuery.trim())
            badges.push({
                key: "author",
                label: `Author: ${adv.authorQuery.trim()}`,
            });
        if (adv.abstractQuery.trim())
            badges.push({
                key: "abstract",
                label: `Abstract: ${adv.abstractQuery.trim()}`,
            });
        if (adv.dateFrom)
            badges.push({ key: "from", label: `From: ${adv.dateFrom}` });
        if (adv.dateTo) badges.push({ key: "to", label: `To: ${adv.dateTo}` });
        filterBadges = badges;
    }

    function validateAdv(): boolean {
        advError = null;
        if (adv.dateFrom && adv.dateTo && adv.dateFrom > adv.dateTo) {
            advError = "Start date must be before end date.";
            return false;
        }
        if (adv.dateFrom && adv.dateFrom > TODAY) {
            advError = "Start date cannot be in the future.";
            return false;
        }
        if (adv.dateTo && adv.dateTo > TODAY) {
            advError = "End date cannot be in the future.";
            return false;
        }
        return true;
    }

    function resetAdv() {
        adv = {
            titleQuery: "",
            dateFrom: "",
            dateTo: "",
            authorQuery: "",
            abstractQuery: "",
            sort: "published_desc",
        };
        advError = null;
    }

    // ─── search debounce ──────────────────────────────────────────────
    let searchTimer: ReturnType<typeof setTimeout> | null = null;
    let query = "";

    async function runSearch() {
        if (!validateAdv()) return;
        const trimmed = query.trim();
        const hasAdv = !!(
            adv.titleQuery.trim() ||
            adv.dateFrom ||
            adv.dateTo ||
            adv.authorQuery.trim() ||
            adv.abstractQuery.trim()
        );

        if (!trimmed && !hasAdv) {
            searchResults = null;
            searchError = null;
            return;
        }

        searchLoading = true;
        searchError = null;

        try {
            // ENTSCHEIDUNG: Global oder Nachbarschaft?
            const isNeighborhoodFilter =
                allowExpand && currentNeighbourIds.length > 0;

            if (isNeighborhoodFilter) {
                // --- PFAD A: Gefilterte Nachbarn (POST) ---
                const res = await fetch(
                    `${apiBaseUrl}/papers/neighbours/filtered`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            entryIds: currentNeighbourIds,
                            filter: {
                                authorQuery:
                                    adv.authorQuery.trim() || undefined,
                                abstractQuery:
                                    adv.abstractQuery.trim() || undefined,
                                dateFrom: adv.dateFrom || undefined,
                                dateTo: adv.dateTo || undefined,
                                titleQuery: adv.titleQuery.trim() || undefined,
                            },
                        }),
                    },
                );

                if (!res.ok) throw new Error(`Server error ${res.status}`);
                const rawItems = await res.json();

                // Mapping der Ergebnisse (wie gewohnt)
                searchResults = rawItems.map(mapPaperResponse);
                searchTotal = searchResults.length;
            } else {
                // --- PFAD B: Globale Suche (GET - dein bestehender Code) ---
                const params = new URLSearchParams();

                // 1. Kategorie-Filter (falls vorhanden, z.B. "cs.AI")
                const safeCat = (categoryFilter || "").replace(
                    /[^a-zA-Z0-9._-]/g,
                    "",
                );
                if (safeCat) params.set("categories", safeCat);

                // 2. Text-Suche kombinieren
                const searchParts: string[] = [];
                if (trimmed) searchParts.push(trimmed);
                if (adv.titleQuery.trim())
                    searchParts.push(adv.titleQuery.trim());
                if (adv.authorQuery.trim())
                    searchParts.push(adv.authorQuery.trim());
                if (adv.abstractQuery.trim())
                    searchParts.push(adv.abstractQuery.trim());

                if (searchParts.length > 0) {
                    // Wir begrenzen die Länge, um keine zu riesigen Header zu senden
                    params.set("search", searchParts.join(" ").slice(0, 300));
                }

                // 3. Datumsfilter
                if (adv.dateFrom) params.set("dateFrom", adv.dateFrom);
                if (adv.dateTo) params.set("dateTo", adv.dateTo);

                // 4. Sortierung
                // Backend erwartet 'published' oder 'citations'
                const backendSort =
                    adv.sort === "citations" ? "citations" : "published";
                params.set("sort", backendSort);

                // 5. Pagination (Die Sicherheitsbremse!)
                // Wir laden nur 30 Paper, damit das 'enrichWithCitations' im Backend
                // nicht mathadventure server
                params.set("take", "100");
                params.set("skip", "0");

                const res = await fetch(
                    `${apiBaseUrl}/papers?${params.toString()}`,
                );
                if (!res.ok) throw new Error(`Server error ${res.status}`);
                const payload = await res.json();
                const rawItems = Array.isArray(payload)
                    ? payload
                    : (payload?.items ?? []);
                searchTotal = Array.isArray(payload)
                    ? rawItems.length
                    : (payload?.total ?? rawItems.length);

                searchResults = rawItems.map(mapPaperResponse);
            }

            dispatch("searchHighlight", searchResults);
        } catch (e) {
            searchError = e instanceof Error ? e.message : "Search failed.";
            searchResults = null;
        } finally {
            searchLoading = false;
        }
    }

    function parseTsne(tsne: unknown): [number, number] {
        if (!tsne) return [0, 0];
        let obj: any = tsne;
        if (typeof obj === "string") {
            try {
                obj = JSON.parse(obj);
            } catch {
                return [0, 0];
            }
        }
        if (
            obj &&
            typeof obj === "object" &&
            typeof obj.x === "number" &&
            typeof obj.y === "number"
        ) {
            return [obj.x, obj.y];
        }
        return [0, 0];
    }

    // Hilfsfunktion zum Mapping, um Code-Duplikate zu vermeiden
    function mapPaperResponse(raw: any) {
        let tsne1 = raw.tsne1 ?? 0,
            tsne2 = raw.tsne2 ?? 0;
        if (tsne1 === 0 && tsne2 === 0 && raw.tsne) {
          const [x, y] = parseTsne(raw.tsne);
          tsne1 = x;
          tsne2 = y;
        }
        return {
            id: Number(raw.id ?? 0),
            entry_id: raw.entry_id,
            title: raw.title ?? raw.entry_id,
            authors: Array.isArray(raw.authors)
                ? raw.authors.join(", ")
                : (raw.authors ?? ""),
            abstract: raw.abstract ?? "",
            published: raw.published ?? null,
            categories: raw.categories ?? null,
            citations: Array.isArray(raw.citations) ? raw.citations : [],
            references: Array.isArray(raw.references) ? raw.references : [],
            non_arxiv_citation_count: Number(raw.non_arxiv_citation_count ?? 0),
            non_arxiv_reference_count: Number(
                raw.non_arxiv_reference_count ?? 0,
            ),
            tsne1,
            tsne2,
            cluster: raw.categories ?? "U",
        };
    }

    // Called when the user clicks the "Search" button in the advanced panel.
    // Builds filter badges for display, runs the search, then tells the graph
    // to highlight author-matching nodes (only when an author query is set -
    // the general searchHighlight event covers all other parameter combinations).
    function applyAdvancedSearch() {
        if (!validateAdv()) return;
        buildBadges();
        runSearch();
        // Only dispatch author highlight when an author query is active.
        // runSearch() will fire searchHighlight for the full results regardless.
        dispatch("authorHighlight", adv.authorQuery.trim());
    }

    function onQueryInput(e: Event) {
        query = (e.currentTarget as HTMLInputElement).value;
        if (searchTimer) clearTimeout(searchTimer);
        if (
            !query.trim() &&
            !adv.dateFrom &&
            !adv.dateTo &&
            !adv.authorQuery.trim()
        ) {
            searchResults = null;
            searchError = null;
            // Notify the graph that there are no active search results to highlight.
            dispatch("searchHighlight", []);
            return;
        }
        searchTimer = setTimeout(runSearch, 400);
    }

    function clearSearch() {
        query = "";
        searchResults = null;
        searchError = null;
        advError = null;
        filterBadges = [];
        if (searchTimer) clearTimeout(searchTimer);
        // Clear both the author highlight and the general search highlight in the graph.
        dispatch("authorHighlight", "");
        dispatch("searchHighlight", []);
    }

    // ─── display list ─────────────────────────────────────────────────
    $: dataSource = searchResults !== null ? searchResults : papers;

    let focusSelected = false;
    let localSelected: Paper | null = null;
    let expandedCitations = new Set<string>();
    let expandedReferences = new Set<string>();

    $: {
        if (selectedPaperId && dataSource && dataSource.length > 0) {
            const found = dataSource.find(
                (p) => p.entry_id === selectedPaperId,
            );
            localSelected = found || null;
            focusSelected = !!found;
            if (found) {
                isOpen = true;
                tick().then(() => {
                    const el = document.querySelector(
                        `[data-paper-id="${selectedPaperId}"]`,
                    ) as HTMLElement | null;
                    if (el)
                        el.scrollIntoView({
                            behavior: "smooth",
                            block: "nearest",
                        });
                });
            }
        } else if (!selectedPaperId) {
            localSelected = null;
            focusSelected = false;
        }
    }

    $: displayedPapers =
        focusSelected && localSelected
            ? [
                  localSelected,
                  ...dataSource.filter(
                      (p) => p.entry_id !== localSelected?.entry_id,
                  ),
              ]
            : dataSource;

    function showAll() {
        focusSelected = false;
        localSelected = null;
    }
    function toggleSidebar() {
        dispatch("toggle");
    }

    function toggleCitations(id: string) {
        if (expandedCitations.has(id)) expandedCitations.delete(id);
        else expandedCitations.add(id);
        expandedCitations = new Set(expandedCitations);
    }
    function toggleReferences(id: string) {
        if (expandedReferences.has(id)) expandedReferences.delete(id);
        else expandedReferences.add(id);
        expandedReferences = new Set(expandedReferences);
    }

    function selectPaper(p: Paper) {
        localSelected = p;
        focusSelected = true;
        query = "";
        dispatch("selectPaper", p);
        tick().then(() => {
            const el = document.querySelector(
                `[data-paper-id="${p.entry_id}"]`,
            ) as HTMLElement | null;
            if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
    }

    function selectCitedPaper(citedId: string) {
        const target = dataSource.find((p) => p.entry_id === citedId);
        if (target) selectPaper(target);
    }

    function getFirstCategory(cats: string | null | undefined): string {
        if (!cats) return "N/A";
        return cats.trim().split(/[\s,]+/)[0] ?? cats;
    }

    function badgeLabel(cats: string | null | undefined): string {
        const cat = getFirstCategory(cats);
        const parts = cat.split(".");
        if (parts.length > 1)
            return parts[parts.length - 1].toUpperCase().slice(0, 4);
        return cat.slice(0, 5).toUpperCase();
    }

    /** Full names for tooltip, one per line: "Artificial Intelligence (cs.AI)\nMachine Learning (cs.LG)" */
    function categoryTooltip(cats: string | null | undefined): string {
        if (!cats) return "";
        const all = cats
            .trim()
            .split(/[\s,]+/)
            .filter(Boolean);
        return all
            .map((cat) => {
                const fullName = getSubcategoryName(cat);
                return fullName && fullName !== cat
                    ? `${fullName} (${cat})`
                    : cat;
            })
            .join("\n");
    }

    /** Full human-readable name for the primary category */
    function categoryFullName(cats: string | null | undefined): string {
        const cat = getFirstCategory(cats);
        const fullName = getSubcategoryName(cat);
        return fullName && fullName !== cat ? fullName : cat;
    }

    /**
     * In cluster/category views, trim extremely long author lists to the first 3 + "et al."
     * In detail/expand mode we show them all.
     */
    function displayAuthors(authors: string, limit = 3): string {
        if (!authors) return "";
        const parts = authors
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        if (parts.length <= limit) return authors;
        return parts.slice(0, limit).join(", ") + ` et al. (${parts.length})`;
    }
</script>

<button
    class="sidebar-toggle"
    class:open={isOpen}
    class:db-blurred={dashboardOpen}
    disabled={dashboardOpen}
    on:click={toggleSidebar}
>
    <span class="toggle-icon">{isOpen ? "\u2192" : "\u2190"}</span>
</button>

<div class="sidebar" class:open={isOpen}>
    <div class="sidebar-header">
        <div class="header-text">
            <span class="header-sup">Academic Papers</span>
            <span class="header-cat">{categoryLabel}</span>
        </div>
        <button class="close-btn" on:click={toggleSidebar}>x</button>
    </div>

    <div class="sidebar-tools">
        <div class="search-row">
            <div class="search">
                <input
                    type="text"
                    placeholder="Search title, authors..."
                    value={query}
                    on:input={onQueryInput}
                />
                {#if query}<button class="clear" on:click={clearSearch}
                        >X</button
                    >{/if}
            </div>
            <button
                class="adv-btn"
                class:active={advancedOpen}
                on:click={() => (advancedOpen = !advancedOpen)}
                title="Advanced search"
            >
                + Filter
            </button>
        </div>

        {#if advancedOpen}
            <div class="adv-panel">
                <div class="adv-row">
                    <label class="adv-label">Title</label>
                    <input
                        class="adv-input"
                        type="text"
                        placeholder="Words in title"
                        maxlength="200"
                        bind:value={adv.titleQuery}
                    />
                </div>
                <div class="adv-row">
                    <label class="adv-label">Author</label>
                    <input
                        class="adv-input"
                        type="text"
                        placeholder="Author name"
                        maxlength="100"
                        bind:value={adv.authorQuery}
                    />
                </div>
                <div class="adv-row">
                    <label class="adv-label">Abstract</label>
                    <input
                        class="adv-input"
                        type="text"
                        placeholder="Text in abstract"
                        maxlength="200"
                        bind:value={adv.abstractQuery}
                    />
                </div>
                <div class="adv-row">
                    <label class="adv-label">From</label>
                    <input
                        class="adv-input"
                        type="date"
                        max={TODAY}
                        bind:value={adv.dateFrom}
                        on:change={() => validateAdv()}
                    />
                </div>
                <div class="adv-row">
                    <label class="adv-label">To</label>
                    <input
                        class="adv-input"
                        type="date"
                        max={TODAY}
                        bind:value={adv.dateTo}
                        on:change={() => validateAdv()}
                    />
                </div>
                <div class="adv-row">
                    <label class="adv-label">Sort by</label>
                    <!-- Two published-date options: newest = most recent papers first,
               oldest = earliest papers first. Most cited sorts by combined citation count. -->
                    <select class="adv-select" bind:value={adv.sort}>
                        <option value="published_desc"
                            >Published date (newest)</option
                        >
                        <option value="published_asc"
                            >Published date (oldest)</option
                        >
                        <option value="citations">Most cited</option>
                    </select>
                </div>
                {#if advError}<p class="adv-error">{advError}</p>{/if}
                <div class="adv-footer">
                    <button
                        class="adv-reset"
                        on:click={() => {
                            resetAdv();
                            clearSearch();
                        }}>Reset</button
                    >
                    <button
                        class="adv-search-btn"
                        on:click={applyAdvancedSearch}>Search</button
                    >
                    {#if searchTotal > 0}<span class="adv-count"
                            >{searchTotal} result{searchTotal !== 1
                                ? "s"
                                : ""}</span
                        >{/if}
                </div>
            </div>
        {/if}

        {#if filterBadges.length > 0}
            <div class="badge-row">
                {#each filterBadges as badge (badge.key)}
                    <span class="filter-badge">{badge.label}</span>
                {/each}
            </div>
        {/if}

        {#if focusSelected}<button class="show-all" on:click={showAll}
                >Show all</button
            >{/if}
    </div>

    <div class="sidebar-content">
        {#if searchLoading}
            <div class="search-status">
                <div class="mini-spinner"></div>
                <span>Searching...</span>
            </div>
        {:else if searchError}
            <div class="search-status error">{searchError}</div>
        {:else if displayedPapers.length === 0}
            <div class="empty">
                {searchResults !== null
                    ? "No results found."
                    : "No papers found."}
            </div>
        {:else}
            {#if searchResults !== null}
                <div class="results-info">
                    {searchResults.length} result{searchResults.length !== 1
                        ? "s"
                        : ""}{categoryFilter ? ` in ${categoryFilter}` : ""}
                </div>
            {/if}
            {#each displayedPapers as paper (paper.entry_id)}
                <!-- svelte-ignore a11y-click-events-have-key-events -->
                <!-- svelte-ignore a11y-no-static-element-interactions -->
                <div
                    class="paper-item"
                    class:selected={selectedPaperId === paper.entry_id}
                    data-paper-id={paper.entry_id}
                    on:click|stopPropagation={() => selectPaper(paper)}
                >
                    <div
                        class="paper-cluster"
                        style="background-color: {getClusterColor(
                            paper.categories,
                            paper.cluster,
                        )}"
                        title={categoryTooltip(paper.categories)}
                    >
                        {badgeLabel(paper.categories)}
                    </div>
                    <div class="paper-info">
                        <p class="paper-category">
                            {categoryFullName(paper.categories)}
                        </p>
                        <h4>{paper.title}</h4>
                        <p class="paper-authors">
                            {allowExpand
                                ? paper.authors
                                : displayAuthors(paper.authors)}
                        </p>
                        <p class="paper-summary">
                            {paper.abstract.length > (allowExpand ? 100 : 160)
                                ? paper.abstract.substring(
                                      0,
                                      allowExpand ? 100 : 160,
                                  ) + "..."
                                : paper.abstract}
                        </p>
                        <div class="paper-meta">
                            {#if allowExpand}
                                <div class="meta-actions">
                                    <button
                                        class="expand-btn citations-btn"
                                        on:click|stopPropagation={() =>
                                            toggleCitations(paper.entry_id)}
                                    >
                                        Citations ({paper.citations?.length ??
                                            0}){paper.non_arxiv_citation_count
                                            ? ` +${paper.non_arxiv_citation_count} ext.`
                                            : ""}
                                        {expandedCitations.has(paper.entry_id)
                                            ? "\u25be"
                                            : "\u25b8"}
                                    </button>
                                    <button
                                        class="expand-btn references-btn"
                                        on:click|stopPropagation={() =>
                                            toggleReferences(paper.entry_id)}
                                    >
                                        References ({paper.references?.length ??
                                            0}){paper.non_arxiv_reference_count
                                            ? ` +${paper.non_arxiv_reference_count} ext.`
                                            : ""}
                                        {expandedReferences.has(paper.entry_id)
                                            ? "\u25be"
                                            : "\u25b8"}
                                    </button>
                                </div>
                            {:else}
                                <span class="meta-counts">
                                    {#if paper.non_arxiv_citation_count || paper.non_arxiv_reference_count || paper.citations?.length || paper.references?.length}
                                        <span class="arxiv-count"
                                            >{paper.citations?.length ?? 0} Citations</span
                                        >
                                        &nbsp;&middot;&nbsp;
                                        <span class="arxiv-count"
                                            >{paper.references?.length ?? 0} References</span
                                        >
                                        {#if (paper.non_arxiv_citation_count ?? 0) + (paper.non_arxiv_reference_count ?? 0) > 0}
                                            &nbsp;&middot;&nbsp;
                                            <span class="non-arxiv-count"
                                                >{(paper.non_arxiv_citation_count ??
                                                    0) +
                                                    (paper.non_arxiv_reference_count ??
                                                        0)} Non-arXiv</span
                                            >
                                        {/if}
                                    {:else}
                                        No citation data
                                    {/if}
                                </span>
                            {/if}
                            <span class="date"
                                >{paper.published
                                    ? new Date(paper.published).getFullYear()
                                    : "\u2014"}</span
                            >
                        </div>

                        {#if allowExpand && expandedCitations.has(paper.entry_id) && (paper.citations?.length ?? 0) > 0}
                            <div class="connected-papers citation-papers">
                                {#each paper.citations as citedId}
                                    {@const citedPaper = dataSource.find(
                                        (p) => p.entry_id === citedId,
                                    )}
                                    {#if citedPaper}
                                        <div
                                            class="connected-item"
                                            on:click|stopPropagation={() =>
                                                selectCitedPaper(citedId)}
                                        >
                                            <h5>{citedPaper.title}</h5>
                                            <p>{citedPaper.authors}</p>
                                        </div>
                                    {:else if !searchResults}
                                        <div class="connected-item placeholder">
                                            Paper data not loaded.
                                        </div>
                                    {/if}
                                {/each}
                            </div>
                        {/if}
                        {#if allowExpand && expandedReferences.has(paper.entry_id) && (paper.references?.length ?? 0) > 0}
                            <div class="connected-papers reference-papers">
                                {#each paper.references as refId}
                                    {@const refPaper = dataSource.find(
                                        (p) => p.entry_id === refId,
                                    )}
                                    {#if refPaper}
                                        <!-- svelte-ignore a11y-click-events-have-key-events -->
                                        <!-- svelte-ignore a11y-no-static-element-interactions -->
                                        <div
                                            class="connected-item ref-item"
                                            on:click|stopPropagation={() =>
                                                selectPaper(refPaper)}
                                        >
                                            <h5>{refPaper.title}</h5>
                                            <p>{refPaper.authors}</p>
                                        </div>
                                    {/if}
                                {/each}
                            </div>
                        {/if}
                    </div>
                </div>
            {/each}
        {/if}
    </div>
</div>

<style>
    .sidebar-toggle {
        position: absolute;
        right: -5px;
        top: 50%;
        transform: translateY(-50%);
        background: linear-gradient(
            135deg,
            var(--accent-purple, #9333ea),
            var(--accent-magenta, #e839a0)
        );
        border: none;
        border-radius: 50% 0 0 50%;
        width: 36px;
        height: 56px;
        color: white;
        cursor: pointer;
        z-index: 200;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 15px rgba(147, 51, 234, 0.3);
    }
    .sidebar-toggle:hover {
        box-shadow: 0 0 25px rgba(147, 51, 234, 0.5);
        transform: translateY(-50%) scale(1.05);
    }
    .sidebar-toggle.open {
        right: 370px;
        border-radius: 0 50% 50% 0;
    }
    .sidebar-toggle.db-blurred {
        filter: blur(3px);
        opacity: 0.4;
        pointer-events: none;
        cursor: default;
    }
    .toggle-icon {
        font-size: 16px;
        font-weight: bold;
    }

    .sidebar {
        position: absolute;
        right: -380px;
        top: 0;
        width: 370px;
        height: 100%;
        background: var(--bg-secondary, #141530);
        border-left: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 150;
        display: flex;
        flex-direction: column;
    }
    .sidebar.open {
        right: 0;
    }

    .sidebar-header {
        padding: 14px 16px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(
            180deg,
            rgba(147, 51, 234, 0.06),
            transparent
        );
        flex-shrink: 0;
    }
    .sidebar-header h3 {
        margin: 0;
        color: var(--text-primary, #f0f0f8);
        font-size: 15px;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .header-text {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 1px;
        overflow: hidden;
    }
    .header-sup {
        font-size: 10px;
        font-weight: 400;
        color: var(--text-muted, #6b6b8d);
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .header-cat {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent-cyan, #22d3ee);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .close-btn {
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        font-size: 22px;
        cursor: pointer;
        padding: 0;
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        transition: all 0.15s ease;
    }
    .close-btn:hover {
        color: var(--text-primary, #f0f0f8);
        background: rgba(147, 51, 234, 0.15);
    }

    .sidebar-tools {
        padding: 8px 10px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        flex-shrink: 0;
    }
    .search-row {
        display: flex;
        gap: 6px;
        align-items: center;
    }
    .search {
        flex: 1;
        position: relative;
    }
    .search input {
        width: 100%;
        padding: 0.45rem 2.2rem 0.45rem 0.7rem;
        border: 1px solid var(--border-subtle, rgba(147, 51, 234, 0.18));
        border-radius: 8px;
        background: rgba(15, 16, 32, 0.6);
        color: var(--text-primary, #f0f0f8);
        outline: none;
        font-size: 13px;
        box-sizing: border-box;
        transition: border-color 0.15s ease;
    }
    .search input:focus {
        border-color: rgba(147, 51, 234, 0.45);
    }
    .search input::placeholder {
        color: var(--text-muted, #6b6b8d);
    }
    .search .clear {
        position: absolute;
        right: 6px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        cursor: pointer;
        padding: 0 4px;
        transition: color 0.15s ease;
    }
    .search .clear:hover {
        color: var(--accent-magenta, #e839a0);
    }

    .adv-btn {
        flex-shrink: 0;
        background: rgba(147, 51, 234, 0.1);
        border: 1px solid rgba(147, 51, 234, 0.2);
        color: var(--text-secondary, #a8a8c8);
        border-radius: 8px;
        padding: 0.42rem 0.7rem;
        cursor: pointer;
        font-size: 12px;
        white-space: nowrap;
        transition: all 0.15s ease;
    }
    .adv-btn:hover,
    .adv-btn.active {
        background: rgba(147, 51, 234, 0.22);
        border-color: rgba(147, 51, 234, 0.4);
        color: var(--text-primary, #f0f0f8);
    }

    .adv-panel {
        margin-top: 8px;
        padding: 8px 10px;
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.07));
        border-radius: 8px;
    }
    .adv-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
    }
    .adv-label {
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        min-width: 50px;
        flex-shrink: 0;
    }
    .adv-input,
    .adv-select {
        flex: 1;
        min-width: 0;
        background: rgba(15, 16, 32, 0.6);
        border: 1px solid rgba(147, 51, 234, 0.2);
        border-radius: 6px;
        color: var(--text-primary, #f0f0f8);
        padding: 4px 8px;
        font-size: 12px;
        outline: none;
    }
    .adv-input:focus,
    .adv-select:focus {
        border-color: rgba(147, 51, 234, 0.5);
    }
    .adv-input::-webkit-calendar-picker-indicator {
        filter: invert(0.6);
    }
    .adv-select option {
        background: #141530;
    }
    .adv-error {
        margin: 4px 0;
        font-size: 11px;
        color: #f56565;
        padding: 4px 6px;
        background: rgba(245, 101, 101, 0.1);
        border-radius: 4px;
    }
    .adv-footer {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 6px;
    }
    .adv-reset {
        background: rgba(245, 101, 101, 0.1);
        border: 1px solid rgba(245, 101, 101, 0.25);
        color: #fca5a5;
        border-radius: 999px;
        padding: 3px 12px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.12s ease;
    }
    .adv-reset:hover {
        background: rgba(245, 101, 101, 0.2);
    }
    .adv-search-btn {
        background: linear-gradient(
            135deg,
            var(--accent-purple, #9333ea),
            var(--accent-magenta, #e839a0)
        );
        border: none;
        color: white;
        border-radius: 999px;
        padding: 3px 14px;
        cursor: pointer;
        font-size: 11px;
        font-weight: 600;
        transition: all 0.12s ease;
        box-shadow: 0 0 8px rgba(147, 51, 234, 0.2);
    }
    .adv-search-btn:hover {
        box-shadow: 0 0 16px rgba(147, 51, 234, 0.4);
    }
    .adv-count {
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
    }

    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        padding: 4px 10px 6px;
    }
    .filter-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 11px;
        background: rgba(147, 51, 234, 0.15);
        border: 1px solid rgba(147, 51, 234, 0.3);
        color: var(--accent-cyan, #22d3ee);
    }

    .show-all {
        margin-top: 6px;
        background: rgba(147, 51, 234, 0.1);
        color: var(--text-primary, #f0f0f8);
        border: 1px solid rgba(147, 51, 234, 0.18);
        border-radius: 8px;
        padding: 0.35rem 0.7rem;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.15s ease;
    }
    .show-all:hover {
        background: rgba(147, 51, 234, 0.2);
    }

    .sidebar-content {
        flex: 1;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: rgba(147, 51, 234, 0.35) transparent;
    }
    .sidebar-content::-webkit-scrollbar {
        width: 5px;
    }
    .sidebar-content::-webkit-scrollbar-thumb {
        background: rgba(147, 51, 234, 0.35);
        border-radius: 3px;
    }

    .search-status {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 14px;
        font-size: 12px;
        color: var(--text-muted, #6b6b8d);
    }
    .search-status.error {
        color: #f56565;
    }
    .mini-spinner {
        width: 14px;
        height: 14px;
        border: 2px solid rgba(147, 51, 234, 0.2);
        border-top-color: var(--accent-cyan, #22d3ee);
        border-radius: 50%;
        animation: spin 0.7s linear infinite;
    }
    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
    .results-info {
        padding: 6px 14px;
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.04));
    }
    .empty {
        color: var(--text-muted, #6b6b8d);
        padding: 1.5rem;
        font-size: 13px;
        text-align: center;
    }

    .paper-item {
        padding: 10px 14px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.06));
        cursor: pointer;
        transition: all 0.15s ease;
        display: flex;
        gap: 0.7rem;
    }
    .paper-item:hover {
        background: rgba(147, 51, 234, 0.08);
    }
    .paper-item.selected {
        background: rgba(147, 51, 234, 0.12);
        border-left: 3px solid var(--accent-purple, #9333ea);
    }

    .paper-cluster {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 11px;
        flex-shrink: 0;
        box-shadow: 0 0 8px rgba(0, 0, 0, 0.3);
        cursor: help;
    }

    .paper-info {
        flex: 1;
        min-width: 0;
    }
    .paper-category {
        margin: 0 0 0.15rem;
        font-size: 10px;
        color: rgba(147, 51, 234, 0.8);
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .paper-info h4 {
        margin: 0 0 0.25rem;
        font-size: 13px;
        color: var(--text-primary, #f0f0f8);
        line-height: 1.3;
        font-weight: 500;
        word-wrap: break-word;
    }
    .paper-authors {
        margin: 0 0 0.25rem;
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        font-style: italic;
    }
    .paper-summary {
        margin: 0 0 0.3rem;
        font-size: 11px;
        color: var(--text-secondary, #a8a8c8);
        line-height: 1.4;
    }

    .paper-meta {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        gap: 4px;
        flex-wrap: wrap;
    }
    .meta-actions {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .meta-counts {
        color: var(--text-muted, #6b6b8d);
        font-size: 11px;
        flex-wrap: wrap;
    }
    .arxiv-count {
        color: var(--text-secondary, #a8a8c8);
        font-size: 10px;
    }
    .non-arxiv-count {
        color: #888;
        font-size: 10px;
    }
    .expand-btn {
        cursor: pointer;
        background: none;
        border: none;
        padding: 0;
        font-size: 11px;
        text-align: left;
        transition: color 0.15s ease;
    }
    .citations-btn {
        color: #ff9999;
    }
    .citations-btn:hover {
        color: #ffd0d0;
    }
    .references-btn {
        color: #7ee8e3;
    }
    .references-btn:hover {
        color: #b5f0ed;
    }
    .date {
        color: var(--text-muted, #6b6b8d);
        flex-shrink: 0;
    }

    .connected-papers {
        margin-top: 0.4rem;
        padding-left: 0.75rem;
    }
    .citation-papers {
        border-left: 2px solid rgba(255, 107, 107, 0.4);
    }
    .reference-papers {
        border-left: 2px solid rgba(78, 205, 196, 0.4);
    }
    .connected-item {
        padding: 0.3rem 0.5rem;
        margin-bottom: 0.2rem;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.15s ease;
        background: rgba(147, 51, 234, 0.05);
    }
    .connected-item:hover {
        background: rgba(147, 51, 234, 0.14);
    }
    .ref-item {
        background: rgba(78, 205, 196, 0.04);
    }
    .ref-item:hover {
        background: rgba(78, 205, 196, 0.1);
    }
    .connected-item h5 {
        margin: 0 0 0.1rem;
        font-size: 11px;
        color: var(--text-primary, #f0f0f8);
    }
    .connected-item p {
        margin: 0;
        font-size: 10px;
        color: var(--text-secondary, #a8a8c8);
    }
</style>
