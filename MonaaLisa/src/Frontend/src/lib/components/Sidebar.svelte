<!--
  Left column: search field with filters, and below it one list.
  - While searching: the results (limited to the current subject or category
    unless "all of arXiv" is ticked). Results are passed up so the paper map
    can highlight them.
  - At the subject levels: the subjects or categories of that level, with a
    bar for their size, as a text alternative to the circles.
  - At the paper level: the papers on the map, most cited first, and in a
    second tab the other categories of the subject to switch to.
-->
<script lang="ts">
    import { untrack } from "svelte";
    import { ChevronLeft, ChevronRight, LoaderCircle, Search, SlidersHorizontal, X } from "@lucide/svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import PaperRow from "$lib/components/PaperRow.svelte";
    import { countPapers, getPapers, type PaperQuery } from "$lib/api";
    import { toPapers, citationCount } from "$lib/paper";
    import { formatCount } from "$lib/categories";
    import type { CategoryNode, Paper } from "$lib/types/paper";

    interface Props {
        /** Category id or prefix the search is limited to, "" = everything */
        scope: string;
        scopeLabel: string;
        /** Categories to browse at the subject levels, empty at the paper level */
        categories: CategoryNode[];
        categoriesTitle: string;
        categoryColor: (item: CategoryNode) => string;
        /** What the category counts are, e.g. "papers in the dataset" */
        categoryUnit: string;
        /** Show the category ids (cs.LG) next to the names */
        showIds: boolean;
        /** Category whose papers are on the map, marked in the list */
        activeCategoryId: string | null;
        onbrowse: (item: CategoryNode) => void;
        /** One level up (e.g. back to all subjects), null at the top */
        up: { label: string; onclick: () => void } | null;
        /** Papers on the map at the paper level */
        papers: Paper[];
        papersTitle: string;
        selectedId: string | null;
        onselect: (paper: Paper) => void;
        onresults: (papers: Paper[]) => void;
    }

    let {
        scope,
        scopeLabel,
        categories,
        categoriesTitle,
        categoryColor,
        categoryUnit,
        showIds,
        activeCategoryId,
        onbrowse,
        up,
        papers,
        papersTitle,
        selectedId,
        onselect,
        onresults,
    }: Props = $props();

    let input = $state<HTMLInputElement>();
    let query = $state("");
    let filtersOpen = $state(false);
    let filters = $state({ title: "", author: "", abstract: "", dateFrom: "", dateTo: "" });
    let everywhere = $state(false);
    let sort = $state<NonNullable<PaperQuery["sort"]>>("relevance");
    /** Nothing matched, the results are similar titles */
    let fuzzy = $state(false);

    let results = $state<Paper[] | null>(null);
    /** null while the matches are still being counted */
    let total = $state<number | null>(0);
    let searching = $state(false);
    let error = $state<string | null>(null);

    /** At the paper level: the papers or the other categories */
    let paperTab = $state<"papers" | "categories">("papers");
    $effect(() => {
        void activeCategoryId;
        paperTab = "papers";
    });

    const largest = $derived(Math.max(1, ...categories.map((c) => c.count)));
    // the backend sorts by the arXiv count only, the list shows all citations
    const ranked = $derived([...papers].sort((a, b) => citationCount(b) - citationCount(a)));
    /**
     * Rows of the ranked list that are drawn. A map can hold 20,000 papers,
     * that many rows make every click take seconds, so the list grows on demand.
     */
    const LIST_STEP = 200;
    let listShown = $state(LIST_STEP);
    $effect(() => {
        void papers;
        listShown = LIST_STEP;
    });

    const activeFilters = $derived(Object.values(filters).filter((v) => v.trim()).length);
    const isSearching = $derived(query.trim() !== "" || activeFilters > 0);
    const searchScope = $derived(everywhere ? "" : scope);
    const searchScopeLabel = $derived(everywhere || !scope ? "all of arXiv" : scopeLabel);

    /** Results asked for, raised by "Show more" */
    const PAGE = 50;
    const MOST = 400;
    let shown = $state(PAGE);
    /** The search without its size, a change starts again with the first page */
    let lastSearch = "";

    // run the search 250ms after the last change of query, filters, sort or scope
    let requestId = 0;
    $effect(() => {
        const params: PaperQuery = {
            search: query.trim(),
            title: filters.title.trim(),
            author: filters.author.trim(),
            abstract: filters.abstract.trim(),
            dateFrom: filters.dateFrom,
            dateTo: filters.dateTo,
            categories: searchScope,
            sort,
            take: shown,
            // the list needs no abstracts
            fields: "map",
            count: "none",
        };
        const search = JSON.stringify({ ...params, take: 0 });
        const more = search === lastSearch;
        lastSearch = search;
        if (!more && shown !== PAGE) {
            shown = PAGE; // runs this effect again
            return;
        }
        if (!isSearching) {
            results = null;
            error = null;
            untrack(() => onresults([]));
            return;
        }
        const id = ++requestId;
        const timer = setTimeout(async () => {
            searching = true;
            error = null;
            try {
                // the list comes first, counting all matches can take seconds
                if (!more) {
                    total = null;
                    countPapers(params)
                        .then((n) => {
                            if (lastSearch === search && !fuzzy) total = n;
                        })
                        .catch(() => {});
                }
                const page = await getPapers(params);
                if (id !== requestId) return; // a newer search started meanwhile
                results = toPapers(page.items);
                fuzzy = page.fuzzy === true;
                if (fuzzy) total = results.length;
                const found = results;
                untrack(() => onresults(found));
            } catch {
                if (id === requestId) error = "Search failed. Please try again.";
            } finally {
                if (id === requestId) searching = false;
            }
        }, 250);
        return () => clearTimeout(timer);
    });

    export function focus() {
        input?.focus();
        input?.select();
    }

    function clear() {
        query = "";
        filters = { title: "", author: "", abstract: "", dateFrom: "", dateTo: "" };
    }

    function onkeydown(event: KeyboardEvent) {
        if (event.key === "Escape" && query) {
            event.stopPropagation();
            query = "";
        }
    }
</script>

<aside class="sidebar" aria-label="Search and browse">
    <div class="search">
        <div class="field-row">
            <Search class="icon" aria-hidden="true" />
            <input
                bind:this={input}
                type="search"
                placeholder="Search {scope ? scopeLabel : 'arXiv'}"
                aria-label="Search papers in {searchScopeLabel}"
                bind:value={query}
                {onkeydown}
            />
            {#if searching}<LoaderCircle class="icon spin" aria-label="Searching" />{/if}
            {#if isSearching}
                <Button variant="ghost" size="sm" icon label="Clear search" onclick={clear}><X /></Button>
            {/if}
            <Button
                variant="ghost"
                size="sm"
                icon
                label="Search options"
                pressed={filtersOpen || activeFilters > 0}
                onclick={() => (filtersOpen = !filtersOpen)}
            >
                <SlidersHorizontal />
            </Button>
        </div>
        <p class="hint">
            Title, author or arXiv id
            {#if scope}
                <label class="everywhere"><input type="checkbox" bind:checked={everywhere} /> All of arXiv</label>
            {/if}
            <kbd>/</kbd>
        </p>

        {#if filtersOpen}
            <div class="filters">
                <label>
                    <span class="label">Title contains</span>
                    <input class="field" bind:value={filters.title} />
                </label>
                <label>
                    <span class="label">Author</span>
                    <input class="field" bind:value={filters.author} />
                </label>
                <label class="wide">
                    <span class="label">Abstract contains</span>
                    <input class="field" bind:value={filters.abstract} />
                </label>
                <label>
                    <span class="label">Published from</span>
                    <input class="field" type="date" bind:value={filters.dateFrom} />
                </label>
                <label>
                    <span class="label">to</span>
                    <input class="field" type="date" bind:value={filters.dateTo} />
                </label>
            </div>
        {/if}
    </div>

    {#if isSearching}
        <div class="list-head">
            <span class="label">
                {#if error}
                    {error}
                {:else if results}
                    {#if fuzzy}
                        Nothing matches exactly. Similar titles in {searchScopeLabel}:
                    {:else if total === null}
                        {results.length === 0 ? "No results" : `First ${results.length} results`} in {searchScopeLabel},
                        counting…
                    {:else}
                        {total.toLocaleString("en")} {total === 1 ? "result" : "results"} in {searchScopeLabel}{total >
                        results.length
                            ? `, showing ${results.length}`
                            : ""}
                    {/if}
                {:else}
                    Searching…
                {/if}
            </span>
            <select class="field sort" bind:value={sort} aria-label="Sort results">
                <option value="relevance">Best match</option>
                <option value="citations">Most cited</option>
                <option value="published">Newest</option>
                <option value="published_asc">Oldest</option>
            </select>
        </div>
        <ul class="list">
            {#each results ?? [] as paper (paper.entry_id)}
                <PaperRow
                    title={paper.title}
                    authors={paper.authors}
                    published={paper.published}
                    categories={paper.categories}
                    active={paper.entry_id === selectedId}
                    onclick={() => onselect(paper)}
                />
            {:else}
                {#if results && !searching}
                    <li class="empty">No papers match this search.</li>
                {/if}
            {/each}
            {#if results && !fuzzy && results.length >= shown && shown < MOST && (total === null || total > results.length)}
                <li>
                    <button class="more" disabled={searching} onclick={() => (shown = Math.min(MOST, shown * 2))}>
                        {searching ? "Loading…" : "Show more"}
                    </button>
                </li>
            {/if}
        </ul>
    {:else}
        {#if up}
            <button class="up" onclick={up.onclick}>
                <ChevronLeft aria-hidden="true" />
                {up.label}
            </button>
        {/if}
        {#if activeCategoryId}
            <div class="switch" role="tablist" aria-label="List">
                <button role="tab" aria-selected={paperTab === "papers"} class:active={paperTab === "papers"} onclick={() => (paperTab = "papers")}>
                    Papers <span class="n">{papers.length.toLocaleString("en")}</span>
                </button>
                <button role="tab" aria-selected={paperTab === "categories"} class:active={paperTab === "categories"} onclick={() => (paperTab = "categories")}>
                    Categories <span class="n">{categories.length}</span>
                </button>
            </div>
        {/if}

        {#if activeCategoryId && paperTab === "papers"}
            <div class="list-head">
                <span class="eyebrow">{papersTitle}</span>
                <span class="eyebrow" title="Citations on arXiv and elsewhere">Cited</span>
            </div>
            <ul class="list">
                {#each ranked.slice(0, listShown) as paper (paper.entry_id)}
                    <PaperRow
                        title={paper.title}
                        authors={paper.authors}
                        published={paper.published}
                        categories={paper.categories}
                        count={citationCount(paper)}
                        countLabel="Citations"
                        active={paper.entry_id === selectedId}
                        onclick={() => onselect(paper)}
                    />
                {:else}
                    <li class="empty">No papers loaded.</li>
                {/each}
                {#if ranked.length > listShown}
                    <li>
                        <button class="more" onclick={() => (listShown += LIST_STEP * 2)}>
                            Show more ({listShown.toLocaleString("en")} of {ranked.length.toLocaleString("en")})
                        </button>
                    </li>
                {/if}
            </ul>
        {:else}
            <div class="list-head">
                <span class="eyebrow">{categoriesTitle}</span>
                <span class="eyebrow" title={categoryUnit}>Papers</span>
            </div>
            <ul class="list">
                {#each categories as item (item.id)}
                    {@const active = item.id === activeCategoryId}
                    <li>
                        <button
                            class="category"
                            class:active
                            aria-current={active ? "true" : undefined}
                            style:--c={categoryColor(item)}
                            onclick={() => onbrowse(item)}
                        >
                            <span class="name">
                                {item.name}
                                {#if showIds}<span class="id">{item.id}</span>{/if}
                            </span>
                            <span class="count" title="{item.count.toLocaleString('en')} {categoryUnit}"
                                >{formatCount(item.count)}</span
                            >
                            <ChevronRight class="chev" aria-hidden="true" />
                            <span class="bar" aria-hidden="true"><i style:width="{(item.count / largest) * 100}%"></i></span>
                        </button>
                    </li>
                {/each}
            </ul>
        {/if}
    {/if}
</aside>

<style>
    .sidebar {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        background: var(--surface);
        border-right: 1px solid var(--border);
    }

    .more {
        display: block;
        width: calc(100% - 28px);
        margin: 8px 14px 14px;
        padding: 7px 0;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        color: var(--text-2);
        font-size: var(--text-sm);
        cursor: pointer;
    }
    .more:hover:not(:disabled) {
        border-color: var(--border-strong);
        color: var(--text);
    }

    .search {
        padding: 12px 14px 10px;
        border-bottom: 1px solid var(--border);
    }
    .field-row {
        display: flex;
        align-items: center;
        gap: 2px;
        height: 34px;
        padding: 0 3px 0 9px;
        border: 1px solid var(--border-strong);
        border-radius: var(--radius);
        background: var(--surface);
    }
    .field-row:focus-within {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px var(--accent-soft);
    }
    .field-row :global(.icon) {
        width: 15px;
        height: 15px;
        color: var(--text-3);
        flex-shrink: 0;
    }
    .field-row :global(.spin) {
        animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
    input[type="search"] {
        flex: 1;
        min-width: 0;
        height: 28px;
        padding: 0 6px;
        border: 0;
        background: none;
        font-size: var(--text-base);
    }
    input[type="search"]:focus {
        outline: none;
    }
    input[type="search"]::placeholder {
        color: var(--text-3);
    }
    input[type="search"]::-webkit-search-cancel-button {
        display: none;
    }
    .hint {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 8px 2px 0;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .everywhere {
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        cursor: pointer;
    }
    .everywhere input {
        margin: 0;
    }
    kbd {
        margin-left: auto;
        padding: 0 5px;
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        color: var(--text-3);
        font-variant-numeric: tabular-nums;
        font-size: 11px;
    }

    .filters {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        gap: 8px 10px;
        padding: 10px 0 4px;
    }
    .filters label {
        display: grid;
        gap: 3px;
        min-width: 0;
    }
    .filters .wide {
        grid-column: 1 / -1;
    }
    .filters .field {
        width: 100%;
        min-width: 0;
    }

    .list-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        min-height: 34px;
        padding: 6px 12px 6px 14px;
        border-bottom: 1px solid var(--border);
    }
    .sort {
        height: 26px;
        font-size: var(--text-xs);
    }
    .list {
        flex: 1;
        min-height: 0;
        margin: 0;
        padding: 6px 0 10px;
        list-style: none;
        overflow-y: auto;
    }
    .empty {
        padding: 12px;
        color: var(--text-3);
        font-size: var(--text-sm);
    }

    .up {
        display: flex;
        align-items: center;
        gap: 4px;
        width: 100%;
        padding: 10px 14px 8px 8px;
        border: 0;
        background: none;
        color: var(--accent);
        font-size: var(--text-sm);
        font-weight: 500;
        text-align: left;
        cursor: pointer;
    }
    .up:hover {
        text-decoration: underline;
        text-underline-offset: 2px;
    }
    .up :global(svg) {
        width: 16px;
        height: 16px;
    }

    .switch {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2px;
        margin: 2px 14px 10px;
        padding: 2px;
        border-radius: var(--radius);
        background: var(--surface-2);
    }
    .switch button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        height: 28px;
        border: 0;
        border-radius: var(--radius-sm);
        background: none;
        color: var(--text-2);
        font-size: var(--text-sm);
        font-weight: 500;
        cursor: pointer;
    }
    .switch button:hover {
        color: var(--text);
    }
    .switch button.active {
        background: var(--surface);
        color: var(--text);
        box-shadow: var(--shadow-card);
    }
    .switch .n {
        color: var(--text-3);
        font-variant-numeric: tabular-nums;
        font-size: var(--text-xs);
        font-weight: 400;
    }

    .category {
        position: relative;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto 14px;
        align-items: center;
        gap: 4px 10px;
        width: 100%;
        padding: 8px 10px 9px 14px;
        border: 0;
        border-left: 2px solid transparent;
        background: none;
        text-align: left;
        cursor: pointer;
    }
    .category:hover {
        background: var(--surface-2);
    }
    .category.active {
        border-left-color: var(--c);
        background: color-mix(in srgb, var(--c) 10%, var(--surface));
    }
    .category .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--text);
        font-size: var(--text-sm);
    }
    .category.active .name {
        font-weight: 600;
    }
    .category .id {
        margin-left: 6px;
        color: var(--text-3);
        font-variant-numeric: tabular-nums;
        font-size: 0.75rem;
    }
    .category .count {
        color: var(--text-2);
        font-variant-numeric: tabular-nums;
        font-size: var(--text-xs);
    }
    .category :global(.chev) {
        width: 14px;
        height: 14px;
        color: var(--text-3);
    }
    .bar {
        grid-column: 1 / -1;
        height: 4px;
        border-radius: 2px;
        background: var(--surface-2);
        overflow: hidden;
    }
    .category:hover .bar {
        background: var(--surface-3);
    }
    .bar i {
        display: block;
        height: 100%;
        min-width: 3px;
        border-radius: 2px;
        background: var(--c);
    }
</style>
