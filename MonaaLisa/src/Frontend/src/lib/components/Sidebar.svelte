<!--
  Left column: search field with filters, and below it one list.
  - While searching: the results (limited to the current subject or category
    unless "all of arXiv" is ticked). Results are passed up so the paper map
    can highlight them.
  - At the subject levels: the categories of that level, as a text alternative
    to the treemap.
  - At the paper level: the papers on the map, most cited first.
-->
<script lang="ts">
    import { untrack } from "svelte";
    import { ChevronRight, LoaderCircle, Search, SlidersHorizontal, X } from "@lucide/svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import PaperRow from "$lib/components/PaperRow.svelte";
    import { getPapers, type PaperQuery } from "$lib/api";
    import { toPapers, citationCount } from "$lib/paper";
    import type { CategoryNode, Paper } from "$lib/types/paper";

    interface Props {
        /** Category id or prefix the search is limited to, "" = everything */
        scope: string;
        scopeLabel: string;
        /** Categories to browse at the subject levels, empty at the paper level */
        categories: CategoryNode[];
        categoriesTitle: string;
        categoryColor: (item: CategoryNode) => string;
        onbrowse: (item: CategoryNode) => void;
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
        onbrowse,
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
    let sort = $state<NonNullable<PaperQuery["sort"]>>("citations");

    let results = $state<Paper[] | null>(null);
    let total = $state(0);
    let searching = $state(false);
    let error = $state<string | null>(null);

    const activeFilters = $derived(Object.values(filters).filter((v) => v.trim()).length);
    const isSearching = $derived(query.trim() !== "" || activeFilters > 0);
    const searchScope = $derived(everywhere ? "" : scope);
    const searchScopeLabel = $derived(everywhere || !scope ? "all of arXiv" : scopeLabel);

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
            take: 50,
        };
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
                const page = await getPapers(params);
                if (id !== requestId) return; // a newer search started meanwhile
                results = toPapers(page.items);
                total = page.total;
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
            Title, authors and abstract.
            {#if scope}
                <label class="everywhere"><input type="checkbox" bind:checked={everywhere} /> Search all of arXiv</label>
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
                    {total.toLocaleString("en")} {total === 1 ? "result" : "results"} in {searchScopeLabel}{total >
                    results.length
                        ? `, showing ${results.length}`
                        : ""}
                {:else}
                    Searching…
                {/if}
            </span>
            <select class="field sort" bind:value={sort} aria-label="Sort results">
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
        </ul>
    {:else if categories.length}
        <div class="list-head">
            <span class="label">{categoriesTitle}</span>
        </div>
        <ul class="list">
            {#each categories as item (item.id)}
                <li>
                    <button class="category" onclick={() => onbrowse(item)}>
                        <i style:background={categoryColor(item)}></i>
                        <span class="name">{item.name}</span>
                        <span class="count" title="Papers on arXiv">{item.count.toLocaleString("en")}</span>
                        <ChevronRight class="chev" aria-hidden="true" />
                    </button>
                </li>
            {/each}
        </ul>
    {:else}
        <div class="list-head">
            <span class="label">{papersTitle}</span>
        </div>
        <ul class="list">
            {#each papers as paper (paper.entry_id)}
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
        </ul>
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
        font-family: var(--font-mono);
        font-size: 11px;
    }

    .filters {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px 10px;
        padding: 10px 0 4px;
    }
    .filters label {
        display: grid;
        gap: 3px;
    }
    .filters .wide {
        grid-column: 1 / -1;
    }
    .filters .field {
        width: 100%;
    }

    .list-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        min-height: 40px;
        padding: 6px 10px 6px 14px;
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

    .category {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        padding: 9px 10px 9px 14px;
        border: 0;
        background: none;
        text-align: left;
        cursor: pointer;
    }
    .category:hover {
        background: var(--surface-2);
    }
    .category i {
        width: 8px;
        height: 8px;
        border-radius: 2px;
        flex-shrink: 0;
    }
    .category .name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: var(--text-sm);
    }
    .category .count {
        color: var(--text-3);
        font-family: var(--font-mono);
        font-size: var(--text-xs);
    }
    .category :global(.chev) {
        width: 14px;
        height: 14px;
        color: var(--text-3);
    }
</style>
