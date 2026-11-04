<!--
  Inspector: the floating panel on the right with everything about one paper.
  Tabs: Overview (abstract), Cites (its references), Cited by, Related.
  The lists come from the shared neighbourhood loader, the network view in
  the middle uses the same data.
-->
<script module lang="ts">
    export type InspectorTab = "overview" | "cites" | "citedBy" | "related";
</script>

<script lang="ts">
    import { ExternalLink, Star, X } from "@lucide/svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import PaperRow from "$lib/components/PaperRow.svelte";
    import Spinner from "$lib/components/ui/Spinner.svelte";
    import { categoryColor, paperContext } from "$lib/categories";
    import { loadNeighbourhood, type Neighbourhood } from "$lib/neighbourhood";
    import { publishedYear } from "$lib/paper";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        paper: Paper;
        tab: InspectorTab;
        isFavorite: boolean;
        /** Author whose papers are highlighted in the network, "" = none */
        highlightedAuthor: string;
        onselect: (paper: Paper) => void;
        onfavorite: () => void;
        onauthor: (name: string) => void;
        onclose: () => void;
    }

    let {
        paper,
        tab = $bindable(),
        isFavorite,
        highlightedAuthor,
        onselect,
        onfavorite,
        onauthor,
        onclose,
    }: Props = $props();

    let data = $state<Neighbourhood | null>(null);
    let error = $state<string | null>(null);
    let listFilter = $state("");
    let listSort = $state<"newest" | "oldest" | "title">("newest");

    $effect(() => {
        const id = paper.entry_id;
        data = null;
        error = null;
        listFilter = "";
        loadNeighbourhood(id)
            .then((result) => {
                if (paper.entry_id === id) data = result;
            })
            .catch(() => {
                if (paper.entry_id === id) error = "Citations could not be loaded.";
            });
    });

    // the fully loaded paper has the abstract even when we came from a short list entry
    const full = $derived(data?.paper ?? paper);
    const context = $derived(paperContext(full.categories));
    const authors = $derived(
        full.authors
            .split(",")
            .map((a) => a.trim())
            .filter(Boolean),
    );
    const arxivUrl = $derived(`https://arxiv.org/abs/${encodeURIComponent(full.entry_id)}`);

    const lists = $derived({
        cites: data?.cites ?? [],
        citedBy: data?.citedBy ?? [],
        related: data?.related ?? [],
    });

    const visible = $derived.by(() => {
        if (tab === "overview") return [];
        const q = listFilter.trim().toLowerCase();
        const items = lists[tab].filter(
            (p) => !q || p.title.toLowerCase().includes(q) || p.authors.toLowerCase().includes(q),
        );
        if (tab === "related") return items; // keep the relevance order
        const time = (p: Paper) => (p.published ? Date.parse(p.published) : 0);
        return [...items].sort((a, b) =>
            listSort === "title"
                ? a.title.localeCompare(b.title)
                : listSort === "newest"
                  ? time(b) - time(a)
                  : time(a) - time(b),
        );
    });

    const tabs = $derived([
        { id: "overview" as const, label: "Overview" },
        { id: "cites" as const, label: "Cites", count: lists.cites.length },
        { id: "citedBy" as const, label: "Cited by", count: lists.citedBy.length },
        { id: "related" as const, label: "Related", count: lists.related.length },
    ]);

    const emptyText: Record<Exclude<InspectorTab, "overview">, string> = {
        cites: "None of the papers it references are in the dataset.",
        citedBy: "No paper in the dataset cites this one yet.",
        related: "No related papers known for this paper.",
    };
</script>

<aside class="inspector card" aria-label="Paper details">
    <header>
        <div class="top">
            <span class="context">
                <i style:background={categoryColor(full.categories)}></i>
                <span class="mono">{context.categoryId}</span>
                {#if context.categoryName && context.categoryName !== context.categoryId}
                    <span>{context.categoryName}</span>
                {/if}
                {#if publishedYear(full.published)}<span>· {publishedYear(full.published)}</span>{/if}
            </span>
            <div class="tools">
                <Button
                    variant="ghost"
                    size="sm"
                    icon
                    label={isFavorite ? "Remove from favorites" : "Add to favorites"}
                    pressed={isFavorite}
                    onclick={onfavorite}
                >
                    <Star fill={isFavorite ? "currentColor" : "none"} />
                </Button>
                <a class="icon-link" href={arxivUrl} target="_blank" rel="noopener noreferrer" title="Open on arXiv">
                    <ExternalLink />
                </a>
                <Button variant="ghost" size="sm" icon label="Close" onclick={onclose}><X /></Button>
            </div>
        </div>

        <h2>{full.title}</h2>

        <p class="authors">
            {#each authors as author, i}
                <button
                    class="author"
                    class:active={highlightedAuthor === author}
                    title="Highlight papers by {author}"
                    onclick={() => onauthor(highlightedAuthor === author ? "" : author)}>{author}</button
                >{i < authors.length - 1 ? ", " : ""}
            {/each}
        </p>
    </header>

    <div class="tabs" role="tablist">
        {#each tabs as t}
            <button role="tab" aria-selected={tab === t.id} class:active={tab === t.id} onclick={() => (tab = t.id)}>
                {t.label}
                {#if t.count !== undefined && data}<span class="count">{t.count}</span>{/if}
            </button>
        {/each}
    </div>

    <div class="content">
        {#if error}
            <p class="note">{error}</p>
        {:else if tab === "overview"}
            {#if full.abstract}
                <p class="abstract">{full.abstract}</p>
            {:else if !data}
                <div class="loading"><Spinner /></div>
            {/if}
            <dl class="facts">
                <div>
                    <dt>Cites</dt>
                    <dd>
                        {data ? lists.cites.length : "…"}
                        {#if data?.externalCites}<small>+{data.externalCites} outside arXiv</small>{/if}
                    </dd>
                </div>
                <div>
                    <dt>Cited by</dt>
                    <dd>
                        {data ? lists.citedBy.length : "…"}
                        {#if data?.externalCitedBy}<small>+{data.externalCitedBy} outside arXiv</small>{/if}
                    </dd>
                </div>
                <div>
                    <dt>arXiv id</dt>
                    <dd class="mono">{full.entry_id}</dd>
                </div>
                {#if full.categories}
                    <div>
                        <dt>Categories</dt>
                        <dd class="mono">{full.categories.split(/\s+/).join(", ")}</dd>
                    </div>
                {/if}
            </dl>
        {:else if !data}
            <div class="loading"><Spinner /></div>
        {:else}
            {#if lists[tab].length > 4}
                <div class="list-tools">
                    <input class="field" placeholder="Filter by title or author" bind:value={listFilter} />
                    {#if tab !== "related"}
                        <select class="field" bind:value={listSort} aria-label="Sort">
                            <option value="newest">Newest</option>
                            <option value="oldest">Oldest</option>
                            <option value="title">Title</option>
                        </select>
                    {/if}
                </div>
            {/if}
            <ul class="list">
                {#each visible as item (item.entry_id)}
                    <PaperRow
                        title={item.title}
                        authors={item.authors}
                        published={item.published}
                        categories={item.categories}
                        onclick={() => onselect(item)}
                    />
                {:else}
                    <li class="note">{listFilter ? "Nothing matches the filter." : emptyText[tab]}</li>
                {/each}
            </ul>
        {/if}
    </div>
</aside>

<style>
    .inspector {
        display: flex;
        flex-direction: column;
        width: var(--panel-width);
        max-height: 100%;
        overflow: hidden;
    }

    header {
        padding: 12px 12px 12px 16px;
    }
    .top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }
    .context {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
        color: var(--text-3);
        font-size: var(--text-xs);
        white-space: nowrap;
        overflow: hidden;
    }
    .context i {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .mono {
        font-family: var(--font-mono);
    }
    .tools {
        display: flex;
        gap: 2px;
        flex-shrink: 0;
    }
    .tools :global([aria-pressed="true"]) {
        color: var(--accent);
    }
    .icon-link {
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        border-radius: var(--radius);
        color: var(--text-2);
    }
    .icon-link:hover {
        background: var(--surface-2);
        color: var(--text);
    }
    .icon-link :global(svg) {
        width: 16px;
        height: 16px;
    }

    h2 {
        margin: 10px 0 6px;
        font-size: var(--text-lg);
        font-weight: 600;
        line-height: 1.3;
        color: var(--text);
        text-wrap: pretty;
    }
    .authors {
        margin: 0;
        color: var(--text-2);
        font-size: var(--text-sm);
        line-height: 1.5;
    }
    .author {
        padding: 0;
        border: 0;
        background: none;
        color: inherit;
        cursor: pointer;
    }
    .author:hover {
        color: var(--text);
        text-decoration: underline;
        text-underline-offset: 2px;
    }
    .author.active {
        color: var(--accent);
    }

    .tabs {
        display: flex;
        gap: 2px;
        padding: 0 8px;
        border-bottom: 1px solid var(--border);
    }
    .tabs button {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 10px 8px;
        border: 0;
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
        background: none;
        color: var(--text-3);
        font-size: var(--text-sm);
        font-weight: 500;
        cursor: pointer;
    }
    .tabs button:hover {
        color: var(--text);
    }
    .tabs button.active {
        color: var(--text);
        border-bottom-color: var(--accent);
    }
    .count {
        color: var(--text-3);
        font-family: var(--font-mono);
        font-size: var(--text-xs);
        font-weight: 400;
    }

    .content {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 12px 8px 12px;
    }
    .abstract {
        margin: 0 8px 20px;
        color: var(--text-2);
        font-size: var(--text-base);
        line-height: 1.65;
        text-wrap: pretty;
    }
    .facts {
        display: grid;
        gap: 10px;
        margin: 0 8px;
        padding-top: 16px;
        border-top: 1px solid var(--border);
    }
    .facts div {
        display: grid;
        grid-template-columns: 96px 1fr;
        gap: 8px;
    }
    dt {
        color: var(--text-3);
        font-size: var(--text-sm);
    }
    dd {
        margin: 0;
        color: var(--text);
        font-size: var(--text-sm);
    }
    dd small {
        margin-left: 6px;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .list-tools {
        display: flex;
        gap: 6px;
        margin: 0 4px 8px;
    }
    .list-tools input {
        flex: 1;
        min-width: 0;
    }
    .list {
        margin: 0;
        padding: 0;
        list-style: none;
    }
    .note {
        margin: 8px;
        color: var(--text-3);
        font-size: var(--text-sm);
    }
    .loading {
        display: grid;
        place-items: center;
        padding: 24px;
    }
</style>
