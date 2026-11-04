<!--
  Search card in the top left corner.
  - The search is limited to the current category (scope).
  - With an empty search it lists the most cited papers of the scope.
  - The filters search title, author and abstract separately (all must match).
  Results are passed up so the paper map can highlight them.
-->
<script lang="ts">
    import { untrack, type Snippet } from "svelte";
    import { ChevronUp, List, LoaderCircle, Search, SlidersHorizontal, X } from "@lucide/svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import PaperRow from "$lib/components/PaperRow.svelte";
    import { getPapers, type PaperQuery } from "$lib/api";
    import { toPapers } from "$lib/paper";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        /** Category id or prefix the search is limited to, "" = everything */
        scope: string;
        scopeLabel: string;
        /** Shown when nothing is searched, most cited first */
        topPapers: Paper[];
        onselect: (paper: Paper) => void;
        onresults: (papers: Paper[]) => void;
        /** Brand click, goes back to all subjects */
        onhome: () => void;
        /** Breadcrumb path, rendered below the search field */
        crumbs?: Snippet;
        /** Whether the paper list is shown, the parent closes it when a paper opens */
        listOpen?: boolean;
    }

    let {
        scope,
        scopeLabel,
        topPapers,
        onselect,
        onresults,
        onhome,
        crumbs,
        listOpen = $bindable(false),
    }: Props = $props();

    let query = $state("");
    let filtersOpen = $state(false);
    let filters = $state({ title: "", author: "", abstract: "", dateFrom: "", dateTo: "" });
    let sort = $state<NonNullable<PaperQuery["sort"]>>("citations");

    let results = $state<Paper[] | null>(null);
    let total = $state(0);
    let searching = $state(false);
    let error = $state<string | null>(null);

    const activeFilters = $derived(Object.values(filters).filter((v) => v.trim()).length);
    const isSearching = $derived(query.trim() !== "" || activeFilters > 0);
    const shown = $derived(results ?? topPapers);

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
            categories: scope,
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

    function clear() {
        query = "";
        filters = { title: "", author: "", abstract: "", dateFrom: "", dateTo: "" };
    }

    function onkeydown(event: KeyboardEvent) {
        if (event.key === "Escape") {
            if (query) query = "";
            else listOpen = false;
        }
    }
</script>

<section class="search card" aria-label="Search papers">
    <div class="field-row">
        <button class="brand" onclick={onhome} title="Monaa-Lisa: back to all subjects" aria-label="Monaa-Lisa home">
            ML
        </button>
        <Search class="icon" aria-hidden="true" />
        <input
            type="search"
            placeholder="Search {scopeLabel}"
            aria-label="Search papers in {scopeLabel}"
            bind:value={query}
            oninput={() => (listOpen = true)}
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
            label="Filters"
            pressed={filtersOpen || activeFilters > 0}
            onclick={() => (filtersOpen = !filtersOpen)}
        >
            <SlidersHorizontal />
        </Button>
        <Button
            variant="ghost"
            size="sm"
            icon
            label={listOpen ? "Hide list" : "Show paper list"}
            pressed={listOpen}
            onclick={() => (listOpen = !listOpen)}
        >
            {#if listOpen}<ChevronUp />{:else}<List />{/if}
        </Button>
    </div>

    {#if crumbs}
        <div class="crumbs">{@render crumbs()}</div>
    {/if}

    {#if filtersOpen}
        <div class="filters">
            <label>
                <span class="label">Title contains</span>
                <input class="field" bind:value={filters.title} oninput={() => (listOpen = true)} />
            </label>
            <label>
                <span class="label">Author</span>
                <input class="field" bind:value={filters.author} oninput={() => (listOpen = true)} />
            </label>
            <label class="wide">
                <span class="label">Abstract contains</span>
                <input class="field" bind:value={filters.abstract} oninput={() => (listOpen = true)} />
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

    {#if listOpen}
        <div class="list-head">
            <span class="label">
                {#if error}
                    {error}
                {:else if results}
                    {total.toLocaleString("en")} {total === 1 ? "result" : "results"} in {scopeLabel}
                {:else}
                    Most cited in {scopeLabel}
                {/if}
            </span>
            {#if results}
                <select class="field sort" bind:value={sort} aria-label="Sort results">
                    <option value="citations">Most cited</option>
                    <option value="published">Newest</option>
                    <option value="published_asc">Oldest</option>
                </select>
            {/if}
        </div>
        <ul class="list">
            {#each shown as paper (paper.entry_id)}
                <PaperRow
                    title={paper.title}
                    authors={paper.authors}
                    published={paper.published}
                    categories={paper.categories}
                    onclick={() => onselect(paper)}
                />
            {:else}
                {#if !searching}
                    <li class="empty">{isSearching ? "No papers match this search." : "No papers loaded yet."}</li>
                {/if}
            {/each}
        </ul>
    {/if}
</section>

<style>
    .search {
        display: flex;
        flex-direction: column;
        width: 380px;
        max-height: calc(100vh - 24px);
        overflow: hidden;
    }

    .field-row {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 6px 6px 6px 6px;
    }
    .brand {
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        margin-right: 6px;
        border: 0;
        border-radius: var(--radius);
        background: var(--accent);
        color: var(--accent-fg);
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        flex-shrink: 0;
    }
    .brand:hover {
        background: var(--accent-hover);
    }
    .field-row :global(.icon) {
        width: 16px;
        height: 16px;
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
        padding: 0 4px;
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

    .crumbs {
        padding: 0 8px 8px 38px;
    }

    .filters {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        padding: 12px;
        border-top: 1px solid var(--border);
    }
    .filters label {
        display: grid;
        gap: 4px;
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
        padding: 4px 8px 4px 12px;
        border-top: 1px solid var(--border);
    }
    .sort {
        height: 26px;
        font-size: var(--text-xs);
    }
    .list {
        margin: 0;
        padding: 0 4px 6px;
        list-style: none;
        overflow-y: auto;
    }
    .empty {
        padding: 12px 10px;
        color: var(--text-3);
        font-size: var(--text-sm);
    }
</style>
