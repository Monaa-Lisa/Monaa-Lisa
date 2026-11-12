<!--
  PaperSidebar.svelte
  Sidebar for the Paper Detail view.
  Shows the selected paper info, history, citations, references with advanced filter.
-->
<script lang="ts">
    import { createEventDispatcher, onMount } from "svelte";
    import { env as publicEnv } from "$env/dynamic/public";
    import type { Paper } from "$lib/types/paper";
    import { getSubcategoryName } from "../utils/arxivTaxonomy";
    import LoadingSpinner from "./LoadingSpinner.svelte";

    export let paper: Paper;
    export let apiBaseUrl: string = publicEnv.PUBLIC_API_BASE_URL || "http://localhost:3000/";
    export let isOpen: boolean = false;
    export let isFavorite: boolean = false;
    /** When true (dashboard is open), the toggle button is blurred and non-interactive. */
    export let dashboardOpen: boolean = false;

    const COLOR_CITATION = "#ff6b6b";
    const COLOR_REFERENCE = "#4ecdc4";

    interface NeighbourPaperItem {
        entry_id: string;
        title: string;
        authors: string;
        abstract: string;
        published: string | null;
        categories: string | null;
        non_arxiv_citation_count: number;
        non_arxiv_reference_count: number;
    }

    const dispatch = createEventDispatcher<{
        toggle: void;
        navigate: Paper;
        favorite: Paper;
        authorHighlight: string;
    }>();

    // ─── UI state ─────────────────────────────────────────────────────
    let citationsOpen = true;
    let referencesOpen = true;
    let abstractExpanded = false;
    let advancedFilterOpen = false;

    // Base filters
    let showCitations = true;
    let showReferences = true;

    // ─── advanced neighbourhood filter ───────────────────────────────
    interface NeighbourFilter {
        dateFrom: string; // YYYY-MM-DD or ''
        dateTo: string;
        authorQuery: string;
        abstractQuery: string;
        onlyArxiv: boolean; // hide entries without arXiv data
        minCitations: string; // '' or number string
    }
    let nFilter: NeighbourFilter = {
        dateFrom: "",
        dateTo: "",
        authorQuery: "",
        abstractQuery: "",
        onlyArxiv: false,
        minCitations: "",
    };
    let filterError: string | null = null;

    const TODAY = new Date().toISOString().slice(0, 10);

    function validateFilter(): boolean {
        filterError = null;
        if (
            nFilter.dateFrom &&
            nFilter.dateTo &&
            nFilter.dateFrom > nFilter.dateTo
        ) {
            filterError = "Start date must be before end date.";
            return false;
        }
        if (nFilter.dateFrom && nFilter.dateFrom > TODAY) {
            filterError = "Start date cannot be in the future.";
            return false;
        }
        if (nFilter.dateTo && nFilter.dateTo > TODAY) {
            filterError = "End date cannot be in the future.";
            return false;
        }
        const mc = parseInt(nFilter.minCitations, 10);
        if (nFilter.minCitations !== "" && (isNaN(mc) || mc < 0)) {
            filterError = "Min. citations must be a non-negative number.";
            return false;
        }
        return true;
    }

    function resetFilter() {
        nFilter = {
            dateFrom: "",
            dateTo: "",
            authorQuery: "",
            abstractQuery: "",
            onlyArxiv: false,
            minCitations: "",
        };
        filterError = null;
        filterBadges = [];
        dispatch("authorHighlight", "");
    }

    // ─── filter badges ──────────────────────────────────────────────
    interface FilterBadge {
        key: string;
        label: string;
    }
    let filterBadges: FilterBadge[] = [];

    function buildFilterBadges() {
        const badges: FilterBadge[] = [];
        if (nFilter.authorQuery.trim())
            badges.push({ key: "author", label: nFilter.authorQuery.trim() });
        if (nFilter.abstractQuery.trim())
            badges.push({
                key: "abstract",
                label: nFilter.abstractQuery.trim(),
            });
        if (nFilter.dateFrom)
            badges.push({
                key: "dateFrom",
                label: `From: ${nFilter.dateFrom}`,
            });
        if (nFilter.dateTo)
            badges.push({ key: "dateTo", label: `To: ${nFilter.dateTo}` });
        if (nFilter.minCitations)
            badges.push({
                key: "minCit",
                label: `Min Cit: ${nFilter.minCitations}`,
            });
        filterBadges = badges;
    }

    function applyFilterAndBadge() {
        if (!validateFilter()) return;
        buildFilterBadges();
        dispatch("authorHighlight", nFilter.authorQuery.trim());
    }

    function applyFilter(items: NeighbourPaperItem[]): NeighbourPaperItem[] {
        return items.filter((item) => {
            if (nFilter.onlyArxiv && !item.entry_id.startsWith("http")) {
                // non-arXiv items typically have non-standard ids – but we filter by whether we have real data
            }
            if (nFilter.dateFrom && item.published) {
                if (item.published.slice(0, 10) < nFilter.dateFrom)
                    return false;
            }
            if (nFilter.dateTo && item.published) {
                if (item.published.slice(0, 10) > nFilter.dateTo) return false;
            }
            if (nFilter.authorQuery.trim()) {
                const q = nFilter.authorQuery.trim().toLowerCase();
                if (!item.authors.toLowerCase().includes(q)) return false;
            }
            if (nFilter.abstractQuery.trim()) {
                const q = nFilter.abstractQuery.trim().toLowerCase();
                if (!item.abstract.toLowerCase().includes(q)) return false;
            }
            const mc = parseInt(nFilter.minCitations, 10);
            if (!isNaN(mc) && nFilter.minCitations !== "") {
                if ((item.non_arxiv_citation_count ?? 0) < mc) return false;
            }
            return true;
        });
    }

    $: hasActiveFilter = !!(
        nFilter.dateFrom ||
        nFilter.dateTo ||
        nFilter.authorQuery.trim() ||
        nFilter.abstractQuery.trim() ||
        nFilter.onlyArxiv ||
        nFilter.minCitations
    );

    // ─── neighbour data ───────────────────────────────────────────────
    let loading = true;
    let errorMsg: string | null = null;
    let citedPapers: NeighbourPaperItem[] = [];
    let citedByPapers: NeighbourPaperItem[] = [];
    let nonArxivCitations = 0;
    let nonArxivReferences = 0;

    let expandedAbstracts = new Set<string>();
    let expandedNested = new Set<string>();
    let nestedData: Record<
        string,
        {
            cites: NeighbourPaperItem[];
            citedBy: NeighbourPaperItem[];
            loading: boolean;
        }
    > = {};
    let focusedId: string | null = null;

    // ─── fetch neighbourhood ──────────────────────────────────────────
    async function fetchNeighbourhood(entryId: string) {
        loading = true;
        errorMsg = null;
        citedPapers = [];
        citedByPapers = [];
        focusedId = null;
        expandedAbstracts = new Set();
        expandedNested = new Set();
        nestedData = {};
        abstractExpanded = false;
        // reset filter when navigating to new paper
        resetFilter();
        advancedFilterOpen = false;

        try {
            const [citRes, refRes] = await Promise.all([
                fetch(
                    `${apiBaseUrl}/paper-citations/paper/${encodeURIComponent(entryId)}`,
                ),
                fetch(
                    `${apiBaseUrl}/paper-references/paper/${encodeURIComponent(entryId)}`,
                ),
            ]);

            const citationsRaw: { cited_paper_entry_id: string }[] = citRes.ok
                ? await citRes.json()
                : [];
            const referencesRaw: { referenced_paper_entry_id: string }[] =
                refRes.ok ? await refRes.json() : [];

            const citedIds = citationsRaw.map((c) => c.cited_paper_entry_id);
            const referencedIds = referencesRaw.map(
                (r) => r.referenced_paper_entry_id,
            );
            const allIds = [...new Set([...citedIds, ...referencedIds])];

            let realPapers: Record<string, NeighbourPaperItem> = {};
            if (allIds.length > 0) {
                const batchSize = 500;
                const batches: string[][] = [];
                for (let i = 0; i < allIds.length; i += batchSize) {
                    batches.push(allIds.slice(i, i + batchSize));
                }
                const results = await Promise.all(
                    batches.map((ids) =>
                        fetch(`${apiBaseUrl}/papers/batch`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ entryIds: ids }),
                        }).then((r) => (r.ok ? r.json() : [])),
                    ),
                );
                results.flat().forEach((p: any) => {
                    realPapers[p.entry_id] = {
                        entry_id: p.entry_id,
                        title: p.title ?? p.entry_id,
                        authors: Array.isArray(p.authors)
                            ? p.authors.join(", ")
                            : (p.authors ?? ""),
                        abstract: p.abstract ?? "",
                        published: p.published ?? null,
                        categories: p.categories ?? null,
                        non_arxiv_citation_count: Number(
                            p.non_arxiv_citation_count ?? 0,
                        ),
                        non_arxiv_reference_count: Number(
                            p.non_arxiv_reference_count ?? 0,
                        ),
                    };
                });
            }

            citedPapers = [...new Set(citedIds)]
                .map((id) => realPapers[id])
                .filter(Boolean);
            citedByPapers = [...new Set(referencedIds)]
                .map((id) => realPapers[id])
                .filter(Boolean);
            nonArxivCitations = paper.non_arxiv_citation_count ?? 0;
            nonArxivReferences = paper.non_arxiv_reference_count ?? 0;
        } catch (e) {
            errorMsg =
                e instanceof Error
                    ? e.message
                    : "Failed to load neighbourhood.";
        } finally {
            loading = false;
        }
    }

    // ─── nested data for focused item ────────────────────────────────
    async function fetchNested(entryId: string) {
        if (nestedData[entryId] !== undefined) return;
        nestedData = {
            ...nestedData,
            [entryId]: { cites: [], citedBy: [], loading: true },
        };
        try {
            const [citRes, refRes] = await Promise.all([
                fetch(
                    `${apiBaseUrl}/paper-citations/paper/${encodeURIComponent(entryId)}`,
                ),
                fetch(
                    `${apiBaseUrl}/paper-references/paper/${encodeURIComponent(entryId)}`,
                ),
            ]);
            const citationsRaw: { cited_paper_entry_id: string }[] = citRes.ok
                ? await citRes.json()
                : [];
            const referencesRaw: { referenced_paper_entry_id: string }[] =
                refRes.ok ? await refRes.json() : [];
            const citedIds = citationsRaw
                .map((c) => c.cited_paper_entry_id)
                .slice(0, 20);
            const citedByIds = referencesRaw
                .map((r) => r.referenced_paper_entry_id)
                .slice(0, 20);
            const allIds = [...new Set([...citedIds, ...citedByIds])];
            let realPapers: Record<string, NeighbourPaperItem> = {};
            if (allIds.length > 0) {
                const raw = await fetch(`${apiBaseUrl}/papers/batch`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ entryIds: allIds }),
                }).then((r) => (r.ok ? r.json() : []));
                raw.forEach((p: any) => {
                    realPapers[p.entry_id] = {
                        entry_id: p.entry_id,
                        title: p.title ?? p.entry_id,
                        authors: Array.isArray(p.authors)
                            ? p.authors.join(", ")
                            : (p.authors ?? ""),
                        abstract: p.abstract ?? "",
                        published: p.published ?? null,
                        categories: p.categories ?? null,
                        non_arxiv_citation_count: Number(
                            p.non_arxiv_citation_count ?? 0,
                        ),
                        non_arxiv_reference_count: Number(
                            p.non_arxiv_reference_count ?? 0,
                        ),
                    };
                });
            }
            nestedData = {
                ...nestedData,
                [entryId]: {
                    cites: citedIds.map((id) => realPapers[id]).filter(Boolean),
                    citedBy: citedByIds
                        .map((id) => realPapers[id])
                        .filter(Boolean),
                    loading: false,
                },
            };
        } catch {
            nestedData = {
                ...nestedData,
                [entryId]: { cites: [], citedBy: [], loading: false },
            };
        }
    }

    // ─── interaction ──────────────────────────────────────────────────
    function navigateTo(item: NeighbourPaperItem) {
        const p: Paper = {
            id: 0,
            entry_id: item.entry_id,
            title: item.title,
            authors: item.authors,
            abstract: item.abstract,
            published: item.published,
            categories: item.categories,
            url: null,
            citations: [],
            references: [],
            non_arxiv_citation_count: item.non_arxiv_citation_count,
            non_arxiv_reference_count: item.non_arxiv_reference_count,
            tsne1: 0,
            tsne2: 0,
            cluster: item.categories ?? "U",
        };
        dispatch("navigate", p);
    }

    function toggleAbstract(entryId: string) {
        if (expandedAbstracts.has(entryId)) expandedAbstracts.delete(entryId);
        else expandedAbstracts.add(entryId);
        expandedAbstracts = new Set(expandedAbstracts);
    }

    function toggleNested(entryId: string) {
        if (expandedNested.has(entryId)) expandedNested.delete(entryId);
        else {
            expandedNested.add(entryId);
            fetchNested(entryId);
        }
        expandedNested = new Set(expandedNested);
    }

    function toggleFocus(entryId: string) {
        focusedId = focusedId === entryId ? null : entryId;
    }

    // ─── format helpers ───────────────────────────────────────────────
    function formatYear(d: string | null): string {
        if (!d) return "-";
        return new Date(d).getFullYear().toString();
    }

    function truncate(s: string, n: number): string {
        return s.length > n ? s.slice(0, n) + "…" : s;
    }

    function firstCat(categories: string | null): string {
        if (!categories) return "";
        const cat = categories.trim().split(/[\s,]+/)[0] ?? "";
        if (!cat) return "";
        const full = getSubcategoryName(cat);
        return full !== cat ? `${full} (${cat})` : cat;
    }

    // ─── reactive reload when paper changes ──────────────────────────
    let lastPaperId = paper?.entry_id;
    $: if (paper?.entry_id && paper.entry_id !== lastPaperId) {
        lastPaperId = paper.entry_id;
        fetchNeighbourhood(paper.entry_id);
    }

    onMount(() => {
        if (paper?.entry_id) fetchNeighbourhood(paper.entry_id);
    });

    $: abstractSnippet = paper?.abstract
        ? paper.abstract.length > 250
            ? paper.abstract.slice(0, 250) + "…"
            : paper.abstract
        : "No abstract available.";

    // filtered lists
    $: filteredCited = applyFilter(citedPapers);
    $: filteredCitedBy = applyFilter(citedByPapers);
</script>

<!-- toggle button -->
<button
    class="sidebar-toggle"
    class:open={isOpen}
    class:db-blurred={dashboardOpen}
    disabled={dashboardOpen}
    on:click={() => dispatch("toggle")}
>
    <span class="toggle-icon">{isOpen ? "→" : "←"}</span>
</button>

<!-- sidebar panel -->
<div class="sidebar" class:open={isOpen}>
    <div class="sidebar-header">
        <h3>Paper Details</h3>
        <button class="close-btn" on:click={() => dispatch("toggle")}>×</button>
    </div>

    <!-- filter chips row -->
    <div class="filter-row">
        <label
            class="filter-chip"
            class:active={showCitations}
            title="Show/hide citations"
        >
            <input type="checkbox" bind:checked={showCitations} />
            <span class="dot" style="background:{COLOR_CITATION}"></span>
            Cites
        </label>
        <label
            class="filter-chip"
            class:active={showReferences}
            title="Show/hide cited-by"
        >
            <input type="checkbox" bind:checked={showReferences} />
            <span class="dot" style="background:{COLOR_REFERENCE}"></span>
            Cited by
        </label>
        <button
            class="adv-filter-btn"
            class:active={advancedFilterOpen || hasActiveFilter}
            on:click={() => {
                advancedFilterOpen = !advancedFilterOpen;
            }}
            title="Advanced filter"
        >
            Filter {hasActiveFilter ? "●" : ""}{advancedFilterOpen
                ? " ▾"
                : " ▸"}
        </button>
    </div>

    <!-- advanced filter panel -->
    {#if advancedFilterOpen}
        <div class="adv-filter-panel">
            <div class="adv-row">
                <label class="adv-label">Published from</label>
                <input
                    class="adv-input"
                    type="date"
                    max={TODAY}
                    bind:value={nFilter.dateFrom}
                    on:change={() => {
                        validateFilter();
                    }}
                />
            </div>
            <div class="adv-row">
                <label class="adv-label">Published to</label>
                <input
                    class="adv-input"
                    type="date"
                    max={TODAY}
                    bind:value={nFilter.dateTo}
                    on:change={() => {
                        validateFilter();
                    }}
                />
            </div>
            <div class="adv-row">
                <label class="adv-label">Author contains</label>
                <input
                    class="adv-input"
                    type="text"
                    placeholder="e.g. Smith"
                    maxlength="100"
                    bind:value={nFilter.authorQuery}
                />
            </div>
            <div class="adv-row">
                <label class="adv-label">Abstract contains</label>
                <input
                    class="adv-input"
                    type="text"
                    placeholder="Text in abstract"
                    maxlength="200"
                    bind:value={nFilter.abstractQuery}
                />
            </div>
            <div class="adv-row">
                <label class="adv-label">Min. arXiv citations</label>
                <input
                    class="adv-input"
                    type="number"
                    min="0"
                    step="1"
                    placeholder="e.g. 5"
                    bind:value={nFilter.minCitations}
                    on:change={() => {
                        validateFilter();
                    }}
                />
            </div>
            {#if filterError}
                <p class="filter-error">{filterError}</p>
            {/if}
            <div class="adv-actions">
                <button class="adv-reset-btn" on:click={resetFilter}
                    >Reset</button
                >
                <button class="adv-search-btn" on:click={applyFilterAndBadge}
                    >Search</button
                >
                <span class="filter-count">
                    {filteredCited.length + filteredCitedBy.length} of {citedPapers.length +
                        citedByPapers.length} shown
                </span>
            </div>
            {#if filterBadges.length > 0}
                <div class="badge-row">
                    {#each filterBadges as badge (badge.key)}
                        <span class="filter-badge">{badge.label}</span>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}

    <div class="sidebar-content">
        <!-- ── selected paper ── -->
        <div class="selected-paper">
            <div class="selected-paper-top">
                <div class="selected-label">Currently Viewing</div>
                <button
                    class="fav-btn"
                    class:fav-active={isFavorite}
                    on:click={() => dispatch("favorite", paper)}
                    title={isFavorite
                        ? "Remove from favorites"
                        : "Add to favorites"}>{isFavorite ? "★" : "☆"}</button
                >
            </div>
            <h4 class="selected-title">{paper.title}</h4>
            <p class="selected-meta">{paper.authors}</p>
            <p class="selected-meta">
                {formatYear(paper.published)}
                {#if paper.categories}&nbsp;·&nbsp;{firstCat(
                        paper.categories,
                    )}{/if}
            </p>
            <!-- citation/reference stats -->
            <div class="stats-row">
                <span class="stat-badge citation-stat" title="arXiv citations">
                    {citedPapers.length} Citations
                </span>
                <span
                    class="stat-badge reference-stat"
                    title="arXiv references"
                >
                    {citedByPapers.length} References
                </span>
                {#if (paper.non_arxiv_citation_count ?? 0) > 0 || (paper.non_arxiv_reference_count ?? 0) > 0}
                    <span
                        class="stat-badge non-arxiv-stat"
                        title="Non-arXiv (external) citations + references"
                    >
                        {(paper.non_arxiv_citation_count ?? 0) +
                            (paper.non_arxiv_reference_count ?? 0)} Non-arXiv
                    </span>
                {/if}
            </div>
            <div class="abstract-block">
                <button
                    class="abstract-toggle"
                    on:click={() => (abstractExpanded = !abstractExpanded)}
                >
                    Abstract {abstractExpanded ? "▾" : "▸"}
                </button>
                <p class="abstract-text">
                    {abstractExpanded
                        ? paper.abstract || "N/A"
                        : abstractSnippet}
                </p>
            </div>
            {#if paper.url}
                <a
                    class="arxiv-link"
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer">Open on arXiv ↗</a
                >
            {/if}
        </div>

        {#if loading}
            <div class="loading-row">
                <LoadingSpinner size={24} /><span>Loading…</span>
            </div>
        {:else if errorMsg}
            <div class="error-row">{errorMsg}</div>
        {:else}
            <!-- ── citations ── -->
            {#if showCitations}
                <div class="section">
                    <button
                        class="section-header citation-header"
                        on:click={() => (citationsOpen = !citationsOpen)}
                    >
                        <span class="section-dot citation-dot"></span>
                        <span class="section-title">
                            Citations ({filteredCited.length}{hasActiveFilter &&
                            filteredCited.length !== citedPapers.length
                                ? `/${citedPapers.length}`
                                : ""}{nonArxivCitations > 0
                                ? ` + ${nonArxivCitations} non-arXiv`
                                : ""})
                        </span>
                        <span class="chevron">{citationsOpen ? "▾" : "▸"}</span>
                    </button>
                    {#if citationsOpen}
                        <div class="paper-list">
                            {#each filteredCited as item (item.entry_id)}
                                <!-- svelte-ignore a11y-click-events-have-key-events -->
                                <!-- svelte-ignore a11y-no-static-element-interactions -->
                                <div
                                    class="paper-item"
                                    class:focused={focusedId === item.entry_id}
                                    on:click={() => toggleFocus(item.entry_id)}
                                    title="Click to expand · click Navigate to open this paper"
                                >
                                    <div
                                        class="item-accent citation-accent"
                                    ></div>
                                    <div class="item-body">
                                        <p class="item-title citation-title">
                                            {item.title}
                                        </p>
                                        <p class="item-meta">
                                            {truncate(item.authors, 50)} · {formatYear(
                                                item.published,
                                            )}
                                        </p>
                                        {#if focusedId === item.entry_id}
                                            <div class="item-abstract-block">
                                                <button
                                                    class="abstract-toggle-inline"
                                                    on:click|stopPropagation={() =>
                                                        toggleAbstract(
                                                            item.entry_id,
                                                        )}
                                                >
                                                    Abstract {expandedAbstracts.has(
                                                        item.entry_id,
                                                    )
                                                        ? "▾"
                                                        : "▸"}
                                                </button>
                                                {#if expandedAbstracts.has(item.entry_id)}
                                                    <p
                                                        class="item-abstract full"
                                                    >
                                                        {item.abstract ||
                                                            "No abstract available."}
                                                    </p>
                                                {:else}
                                                    <p class="item-abstract">
                                                        {item.abstract
                                                            ? truncate(
                                                                  item.abstract,
                                                                  200,
                                                              )
                                                            : "No abstract."}
                                                    </p>
                                                {/if}
                                            </div>
                                            <div class="item-actions">
                                                <button
                                                    class="action-btn"
                                                    on:click|stopPropagation={() =>
                                                        toggleNested(
                                                            item.entry_id,
                                                        )}
                                                >
                                                    {expandedNested.has(
                                                        item.entry_id,
                                                    )
                                                        ? "Less ▴"
                                                        : "Its network ▾"}
                                                </button>
                                                <button
                                                    class="navigate-btn"
                                                    on:click|stopPropagation={() =>
                                                        navigateTo(item)}
                                                >
                                                    Navigate ↗
                                                </button>
                                            </div>
                                            {#if expandedNested.has(item.entry_id)}
                                                {#if nestedData[item.entry_id]?.loading}
                                                    <div
                                                        class="loading-row small"
                                                    >
                                                        <LoadingSpinner
                                                            size={20}
                                                        /><span>Loading…</span>
                                                    </div>
                                                {:else}
                                                    {@const nd =
                                                        nestedData[
                                                            item.entry_id
                                                        ]}
                                                    {#if nd && (nd.cites.length > 0 || nd.citedBy.length > 0)}
                                                        <div
                                                            class="nested-section"
                                                        >
                                                            {#if nd.cites.length > 0}
                                                                <p
                                                                    class="nested-label citation-label"
                                                                >
                                                                    Cites ({nd
                                                                        .cites
                                                                        .length})
                                                                </p>
                                                                {#each nd.cites.slice(0, 8) as nc}
                                                                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                                                                    <!-- svelte-ignore a11y-no-static-element-interactions -->
                                                                    <div
                                                                        class="nested-item"
                                                                        on:click|stopPropagation={() =>
                                                                            navigateTo(
                                                                                nc,
                                                                            )}
                                                                    >
                                                                        <span
                                                                            class="nested-title"
                                                                            >{truncate(
                                                                                nc.title,
                                                                                60,
                                                                            )}</span
                                                                        >
                                                                    </div>
                                                                {/each}
                                                            {/if}
                                                            {#if nd.citedBy.length > 0}
                                                                <p
                                                                    class="nested-label reference-label"
                                                                >
                                                                    Cited by ({nd
                                                                        .citedBy
                                                                        .length})
                                                                </p>
                                                                {#each nd.citedBy.slice(0, 8) as nr}
                                                                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                                                                    <!-- svelte-ignore a11y-no-static-element-interactions -->
                                                                    <div
                                                                        class="nested-item"
                                                                        on:click|stopPropagation={() =>
                                                                            navigateTo(
                                                                                nr,
                                                                            )}
                                                                    >
                                                                        <span
                                                                            class="nested-title"
                                                                            >{truncate(
                                                                                nr.title,
                                                                                60,
                                                                            )}</span
                                                                        >
                                                                    </div>
                                                                {/each}
                                                            {/if}
                                                        </div>
                                                    {:else}
                                                        <p class="nested-empty">
                                                            No connected papers
                                                            found.
                                                        </p>
                                                    {/if}
                                                {/if}
                                            {/if}
                                        {/if}
                                    </div>
                                </div>
                            {/each}
                            {#if filteredCited.length === 0}
                                <p class="empty-msg">
                                    {citedPapers.length === 0
                                        ? "No arXiv citations found."
                                        : "No citations match the filter."}
                                </p>
                            {/if}
                        </div>
                    {/if}
                </div>
            {/if}

            <!-- ── cited by ── -->
            {#if showReferences}
                <div class="section">
                    <button
                        class="section-header reference-header"
                        on:click={() => (referencesOpen = !referencesOpen)}
                    >
                        <span class="section-dot reference-dot"></span>
                        <span class="section-title">
                            References ({filteredCitedBy.length}{hasActiveFilter &&
                            filteredCitedBy.length !== citedByPapers.length
                                ? `/${citedByPapers.length}`
                                : ""}{nonArxivReferences > 0
                                ? ` + ${nonArxivReferences} non-arXiv`
                                : ""})
                        </span>
                        <span class="chevron">{referencesOpen ? "▾" : "▸"}</span
                        >
                    </button>
                    {#if referencesOpen}
                        <div class="paper-list">
                            {#each filteredCitedBy as item (item.entry_id)}
                                <!-- svelte-ignore a11y-click-events-have-key-events -->
                                <!-- svelte-ignore a11y-no-static-element-interactions -->
                                <div
                                    class="paper-item"
                                    class:focused={focusedId === item.entry_id}
                                    on:click={() => toggleFocus(item.entry_id)}
                                    title="Click to expand · click Navigate to open this paper"
                                >
                                    <div
                                        class="item-accent reference-accent"
                                    ></div>
                                    <div class="item-body">
                                        <p class="item-title reference-title">
                                            {item.title}
                                        </p>
                                        <p class="item-meta">
                                            {truncate(item.authors, 50)} · {formatYear(
                                                item.published,
                                            )}
                                        </p>
                                        {#if focusedId === item.entry_id}
                                            <div class="item-abstract-block">
                                                <button
                                                    class="abstract-toggle-inline"
                                                    on:click|stopPropagation={() =>
                                                        toggleAbstract(
                                                            item.entry_id,
                                                        )}
                                                >
                                                    Abstract {expandedAbstracts.has(
                                                        item.entry_id,
                                                    )
                                                        ? "▾"
                                                        : "▸"}
                                                </button>
                                                {#if expandedAbstracts.has(item.entry_id)}
                                                    <p
                                                        class="item-abstract full"
                                                    >
                                                        {item.abstract ||
                                                            "No abstract available."}
                                                    </p>
                                                {:else}
                                                    <p class="item-abstract">
                                                        {item.abstract
                                                            ? truncate(
                                                                  item.abstract,
                                                                  200,
                                                              )
                                                            : "No abstract."}
                                                    </p>
                                                {/if}
                                            </div>
                                            <div class="item-actions">
                                                <button
                                                    class="action-btn"
                                                    on:click|stopPropagation={() =>
                                                        toggleNested(
                                                            item.entry_id,
                                                        )}
                                                >
                                                    {expandedNested.has(
                                                        item.entry_id,
                                                    )
                                                        ? "Less ▴"
                                                        : "Its network ▾"}
                                                </button>
                                                <button
                                                    class="navigate-btn reference-navigate"
                                                    on:click|stopPropagation={() =>
                                                        navigateTo(item)}
                                                >
                                                    Navigate ↗
                                                </button>
                                            </div>
                                            {#if expandedNested.has(item.entry_id)}
                                                {#if nestedData[item.entry_id]?.loading}
                                                    <div
                                                        class="loading-row small"
                                                    >
                                                        <LoadingSpinner
                                                            size={20}
                                                        /><span>Loading…</span>
                                                    </div>
                                                {:else}
                                                    {@const nd =
                                                        nestedData[
                                                            item.entry_id
                                                        ]}
                                                    {#if nd && (nd.cites.length > 0 || nd.citedBy.length > 0)}
                                                        <div
                                                            class="nested-section"
                                                        >
                                                            {#if nd.cites.length > 0}
                                                                <p
                                                                    class="nested-label citation-label"
                                                                >
                                                                    Cites ({nd
                                                                        .cites
                                                                        .length})
                                                                </p>
                                                                {#each nd.cites.slice(0, 8) as nc}
                                                                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                                                                    <!-- svelte-ignore a11y-no-static-element-interactions -->
                                                                    <div
                                                                        class="nested-item"
                                                                        on:click|stopPropagation={() =>
                                                                            navigateTo(
                                                                                nc,
                                                                            )}
                                                                    >
                                                                        <span
                                                                            class="nested-title"
                                                                            >{truncate(
                                                                                nc.title,
                                                                                60,
                                                                            )}</span
                                                                        >
                                                                    </div>
                                                                {/each}
                                                            {/if}
                                                            {#if nd.citedBy.length > 0}
                                                                <p
                                                                    class="nested-label reference-label"
                                                                >
                                                                    Cited by ({nd
                                                                        .citedBy
                                                                        .length})
                                                                </p>
                                                                {#each nd.citedBy.slice(0, 8) as nr}
                                                                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                                                                    <!-- svelte-ignore a11y-no-static-element-interactions -->
                                                                    <div
                                                                        class="nested-item"
                                                                        on:click|stopPropagation={() =>
                                                                            navigateTo(
                                                                                nr,
                                                                            )}
                                                                    >
                                                                        <span
                                                                            class="nested-title"
                                                                            >{truncate(
                                                                                nr.title,
                                                                                60,
                                                                            )}</span
                                                                        >
                                                                    </div>
                                                                {/each}
                                                            {/if}
                                                        </div>
                                                    {:else}
                                                        <p class="nested-empty">
                                                            No connected papers
                                                            found.
                                                        </p>
                                                    {/if}
                                                {/if}
                                            {/if}
                                        {/if}
                                    </div>
                                </div>
                            {/each}
                            {#if filteredCitedBy.length === 0}
                                <p class="empty-msg">
                                    {citedByPapers.length === 0
                                        ? "No arXiv citing papers found."
                                        : "No references match the filter."}
                                </p>
                            {/if}
                        </div>
                    {/if}
                </div>
            {/if}
        {/if}
    </div>
</div>

<style>
    /* ── toggle button ── */
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
        right: calc(var(--sidebar-width, 385px) - 5px);
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

    /* ── sidebar panel ── */
    .sidebar {
        position: absolute;
        right: -400px;
        top: 0;
        --sidebar-width: 385px;
        width: var(--sidebar-width);
        height: 100%;
        background: var(--bg-secondary, #141530);
        border-left: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 150;
        display: flex;
        flex-direction: column;
        overflow: hidden;
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
            rgba(147, 51, 234, 0.08),
            transparent
        );
        flex-shrink: 0;
    }
    .sidebar-header h3 {
        margin: 0;
        color: var(--text-primary, #f0f0f8);
        font-size: 15px;
        font-weight: 600;
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

    /* ── filter row ── */
    .filter-row {
        display: flex;
        gap: 6px;
        padding: 8px 12px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.06));
        flex-shrink: 0;
        align-items: center;
        flex-wrap: wrap;
    }
    .filter-chip {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 3px 10px;
        border-radius: 999px;
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.1));
        background: rgba(255, 255, 255, 0.04);
        color: var(--text-muted, #6b6b8d);
        cursor: pointer;
        font-size: 12px;
        transition: all 0.15s ease;
        user-select: none;
    }
    .filter-chip input {
        display: none;
    }
    .filter-chip.active {
        border-color: rgba(147, 51, 234, 0.35);
        background: rgba(147, 51, 234, 0.12);
        color: var(--text-primary, #f0f0f8);
    }
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }
    .adv-filter-btn {
        margin-left: auto;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.1));
        color: var(--text-muted, #6b6b8d);
        border-radius: 999px;
        padding: 3px 12px;
        cursor: pointer;
        font-size: 11px;
        transition: all 0.15s ease;
        white-space: nowrap;
    }
    .adv-filter-btn:hover,
    .adv-filter-btn.active {
        background: rgba(147, 51, 234, 0.15);
        color: var(--text-primary, #f0f0f8);
        border-color: rgba(147, 51, 234, 0.35);
    }

    /* ── advanced filter panel ── */
    .adv-filter-panel {
        padding: 10px 14px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.06));
        background: rgba(0, 0, 0, 0.2);
        flex-shrink: 0;
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
        min-width: 110px;
        flex-shrink: 0;
    }
    .adv-input {
        flex: 1;
        background: rgba(15, 16, 32, 0.6);
        border: 1px solid rgba(147, 51, 234, 0.2);
        border-radius: 6px;
        color: var(--text-primary, #f0f0f8);
        padding: 4px 8px;
        font-size: 12px;
        outline: none;
        min-width: 0;
    }
    .adv-input:focus {
        border-color: rgba(147, 51, 234, 0.5);
    }
    .adv-input::-webkit-calendar-picker-indicator {
        filter: invert(0.6);
    }
    .filter-error {
        margin: 4px 0;
        font-size: 11px;
        color: #f56565;
        padding: 4px 6px;
        background: rgba(245, 101, 101, 0.1);
        border-radius: 4px;
        border: 1px solid rgba(245, 101, 101, 0.2);
    }
    .adv-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
    }
    .adv-reset-btn {
        background: rgba(245, 101, 101, 0.1);
        border: 1px solid rgba(245, 101, 101, 0.25);
        color: #fca5a5;
        border-radius: 999px;
        padding: 3px 12px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.12s ease;
    }
    .adv-reset-btn:hover {
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
    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 6px;
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
    .filter-count {
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
    }

    /* ── scroll area ── */
    .sidebar-content {
        flex: 1;
        overflow-y: auto;
        padding-bottom: 1rem;
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

    /* ── selected paper ── */
    .selected-paper {
        padding: 14px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.06));
        background: linear-gradient(
            180deg,
            rgba(147, 51, 234, 0.05),
            transparent
        );
    }
    .selected-paper-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 6px;
        margin-bottom: 4px;
    }
    .fav-btn {
        background: none;
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: var(--text-muted, #6b6b8d);
        border-radius: 8px;
        width: 28px;
        height: 28px;
        cursor: pointer;
        font-size: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: all 0.15s ease;
    }
    .fav-btn:hover {
        background: rgba(255, 209, 102, 0.15);
        color: var(--accent-yellow, #ffd166);
        border-color: rgba(255, 209, 102, 0.35);
    }
    .fav-active {
        color: var(--accent-yellow, #ffd166) !important;
        background: rgba(255, 209, 102, 0.12) !important;
        border-color: rgba(255, 209, 102, 0.3) !important;
    }
    .selected-label {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--accent-purple, #9333ea);
        margin-bottom: 4px;
        font-weight: 600;
    }
    .selected-title {
        margin: 0 0 6px;
        font-size: 14px;
        color: var(--text-primary, #f0f0f8);
        line-height: 1.4;
        font-weight: 600;
    }
    .selected-meta {
        margin: 2px 0;
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        font-style: italic;
    }
    .stats-row {
        display: flex;
        gap: 6px;
        margin: 8px 0 4px;
        flex-wrap: wrap;
    }
    .stat-badge {
        font-size: 10px;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .citation-stat {
        color: #ff9999;
        background: rgba(255, 107, 107, 0.1);
        border-color: rgba(255, 107, 107, 0.2);
    }
    .reference-stat {
        color: #7ee8e3;
        background: rgba(78, 205, 196, 0.1);
        border-color: rgba(78, 205, 196, 0.2);
    }
    .non-arxiv-stat {
        color: #a0a0b8;
        background: rgba(100, 100, 130, 0.12);
        border-color: rgba(100, 100, 130, 0.22);
    }
    .item-abstract-block {
        margin: 5px 0 4px;
    }
    .abstract-toggle-inline {
        background: none;
        border: none;
        color: var(--accent-purple, #9333ea);
        cursor: pointer;
        font-size: 11px;
        padding: 0;
        font-weight: 500;
        margin-bottom: 3px;
    }
    .abstract-block {
        margin-top: 8px;
    }
    .abstract-toggle {
        background: none;
        border: none;
        color: var(--accent-purple, #9333ea);
        cursor: pointer;
        font-size: 11px;
        padding: 0;
        font-weight: 500;
        margin-bottom: 3px;
    }
    .abstract-text {
        margin: 0;
        font-size: 11px;
        color: var(--text-secondary, #a8a8c8);
        line-height: 1.5;
    }
    .arxiv-link {
        display: inline-block;
        margin-top: 6px;
        font-size: 11px;
        color: var(--accent-cyan, #22d3ee);
        text-decoration: none;
    }
    .arxiv-link:hover {
        text-decoration: underline;
    }

    /* ── section ── */
    .section {
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.05));
    }
    .section-header {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        background: none;
        border: none;
        cursor: pointer;
        padding: 10px 14px;
        color: var(--text-secondary, #a8a8c8);
        font-size: 12px;
        font-weight: 600;
        text-align: left;
        transition: background 0.15s ease;
    }
    .section-header:hover {
        background: rgba(255, 255, 255, 0.03);
    }
    .citation-header:hover {
        background: rgba(255, 107, 107, 0.05);
    }
    .reference-header:hover {
        background: rgba(78, 205, 196, 0.05);
    }
    .section-icon {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        background: rgba(147, 51, 234, 0.2);
        color: var(--accent-purple, #9333ea);
        font-size: 10px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .section-title {
        flex: 1;
    }
    .chevron {
        font-size: 10px;
        opacity: 0.6;
    }
    .section-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .citation-dot {
        background: #ff6b6b;
        box-shadow: 0 0 5px #ff6b6b66;
    }
    .reference-dot {
        background: #4ecdc4;
        box-shadow: 0 0 5px #4ecdc466;
    }

    /* ── paper list ── */
    .paper-list {
        padding: 4px 0;
    }
    .paper-item {
        display: flex;
        padding: 8px 14px 8px 10px;
        cursor: pointer;
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        transition: background 0.12s ease;
        gap: 8px;
    }
    .paper-item:hover {
        background: rgba(255, 255, 255, 0.03);
    }
    .paper-item.focused {
        background: rgba(147, 51, 234, 0.06);
        border-left: 2px solid var(--accent-purple, #9333ea);
    }
    .item-accent {
        width: 3px;
        border-radius: 3px;
        flex-shrink: 0;
        align-self: stretch;
    }
    .citation-accent {
        background: linear-gradient(
            to bottom,
            #ff6b6b,
            rgba(255, 107, 107, 0.2)
        );
    }
    .reference-accent {
        background: linear-gradient(
            to bottom,
            #4ecdc4,
            rgba(78, 205, 196, 0.2)
        );
    }
    .item-body {
        flex: 1;
        min-width: 0;
    }
    .item-title {
        margin: 0 0 3px;
        font-size: 12px;
        line-height: 1.4;
        font-weight: 500;
        word-break: break-word;
    }
    .citation-title {
        color: #ffa0a0;
    }
    .reference-title {
        color: #7ee8e3;
    }
    .item-meta {
        margin: 0 0 4px;
        font-size: 10px;
        color: var(--text-muted, #6b6b8d);
        font-style: italic;
    }
    .item-abstract {
        margin: 4px 0;
        font-size: 11px;
        color: var(--text-secondary, #a8a8c8);
        line-height: 1.4;
    }
    .item-abstract.full {
        color: var(--text-primary, #f0f0f8);
    }
    .item-actions {
        display: flex;
        gap: 6px;
        margin-top: 6px;
        flex-wrap: wrap;
    }
    .action-btn {
        background: rgba(147, 51, 234, 0.12);
        border: 1px solid rgba(147, 51, 234, 0.2);
        color: var(--text-secondary, #a8a8c8);
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 10px;
        cursor: pointer;
        transition: all 0.12s ease;
    }
    .action-btn:hover {
        background: rgba(147, 51, 234, 0.22);
        color: var(--text-primary, #f0f0f8);
    }
    .navigate-btn {
        background: rgba(255, 107, 107, 0.15);
        border: 1px solid rgba(255, 107, 107, 0.3);
        color: #ffa0a0;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 10px;
        cursor: pointer;
        transition: all 0.12s ease;
        font-weight: 600;
    }
    .navigate-btn:hover {
        background: rgba(255, 107, 107, 0.25);
        color: #fff;
    }
    .reference-navigate {
        background: rgba(78, 205, 196, 0.15);
        border-color: rgba(78, 205, 196, 0.3);
        color: #7ee8e3;
    }
    .reference-navigate:hover {
        background: rgba(78, 205, 196, 0.25);
        color: #fff;
    }

    /* ── nested ── */
    .nested-section {
        margin-top: 6px;
        padding: 6px 8px;
        border-radius: 6px;
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .nested-label {
        margin: 4px 0 2px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .citation-label {
        color: #ff6b6b;
    }
    .reference-label {
        color: #4ecdc4;
    }
    .nested-item {
        padding: 3px 4px;
        cursor: pointer;
        border-radius: 4px;
        transition: background 0.1s ease;
    }
    .nested-item:hover {
        background: rgba(147, 51, 234, 0.1);
    }
    .nested-title {
        font-size: 11px;
        color: var(--text-secondary, #a8a8c8);
        line-height: 1.3;
    }
    .nested-empty {
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        padding: 4px 0;
        margin: 0;
    }

    /* ── history ── */
    .history-list {
        padding: 4px 0;
    }
    .history-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .history-info {
        flex: 1;
        min-width: 0;
    }
    .history-title {
        margin: 0 0 2px;
        font-size: 11px;
        color: var(--text-secondary, #a8a8c8);
        font-weight: 500;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .history-meta {
        margin: 0;
        font-size: 10px;
        color: var(--text-muted, #6b6b8d);
        font-style: italic;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .history-actions {
        display: flex;
        gap: 4px;
        flex-shrink: 0;
    }
    .history-nav-btn,
    .history-del-btn {
        background: none;
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: var(--text-muted, #6b6b8d);
        border-radius: 6px;
        width: 22px;
        height: 22px;
        cursor: pointer;
        font-size: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.12s ease;
    }
    .history-nav-btn:hover {
        background: rgba(34, 211, 238, 0.15);
        color: var(--accent-cyan, #22d3ee);
        border-color: rgba(34, 211, 238, 0.35);
    }
    .history-del-btn:hover {
        background: rgba(245, 101, 101, 0.15);
        color: #f56565;
        border-color: rgba(245, 101, 101, 0.35);
    }

    /* ── misc ── */
    .loading-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 14px;
        color: var(--text-muted, #6b6b8d);
        font-size: 12px;
    }
    .loading-row.small {
        padding: 6px 0;
        font-size: 11px;
    }
    .error-row {
        padding: 10px 14px;
        color: #f56565;
        font-size: 12px;
    }
    .empty-msg {
        padding: 8px 14px;
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        margin: 0;
    }
</style>
