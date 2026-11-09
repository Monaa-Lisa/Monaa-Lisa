<!--
  Details of one paper in the right column: metadata, links, the abstract,
  and the lists of references, citations and related papers. The lists come
  from the shared neighbourhood loader, the citation view in the middle uses
  the same data.
-->
<script module lang="ts">
    export type DetailsTab = "abstract" | "cites" | "citedBy" | "related";
</script>

<script lang="ts">
    import { ArrowLeft, ArrowUpRight, Check, Copy, Crosshair, FileText, Star, X } from "@lucide/svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import PaperRow from "$lib/components/PaperRow.svelte";
    import Spinner from "$lib/components/ui/Spinner.svelte";
    import { categoryColor, paperContext, subcategoryName } from "$lib/categories";
    import {
        loadConnected,
        loadNeighbourhood,
        type Connected,
        type Neighbourhood,
        type SimilarBy,
    } from "$lib/neighbourhood";
    import { authorList, categoryList, citationCount, formatDate, paperLinks, toBibtex } from "$lib/paper";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        paper: Paper;
        tab: DetailsTab;
        /** How the Similar tab finds its papers */
        similarBy?: SimilarBy;
        isFavorite: boolean;
        /** Author whose papers are highlighted on the map, "" = none */
        highlightedAuthor: string;
        /** Title of the previously opened paper, shown on the back button */
        backTo: string | null;
        onback: () => void;
        onselect: (paper: Paper) => void;
        onfavorite: () => void;
        onauthor: (name: string) => void;
        /** False when the paper is already marked on its category map */
        canLocate: boolean;
        /** Opens the map of the paper's category with the paper marked */
        onlocate: () => void;
        onclose: () => void;
    }

    let {
        paper,
        similarBy = $bindable("content"),
        tab = $bindable(),
        isFavorite,
        highlightedAuthor,
        backTo,
        onback,
        onselect,
        onfavorite,
        onauthor,
        canLocate,
        onlocate,
        onclose,
    }: Props = $props();

    let data = $state<Neighbourhood | null>(null);
    let error = $state<string | null>(null);
    let listFilter = $state("");
    let listSort = $state<"citations" | "newest" | "oldest">("citations");
    let copied = $state(false);

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
                if (paper.entry_id === id) error = "The references and citations could not be loaded.";
            });
    });

    // the fully loaded paper has the abstract even when we came from a short list entry
    const full = $derived(data?.paper ?? paper);
    const context = $derived(paperContext(full.categories));
    const authors = $derived(authorList(full.authors));
    const links = $derived(paperLinks(full));
    const categories = $derived(categoryList(full.categories));

    // papers connected through the citation graph, loaded when that way of the Similar tab is chosen
    let connected = $state<Connected | null>(null);
    $effect(() => {
        const id = paper.entry_id;
        const by = similarBy;
        connected = null;
        if (by === "content") return;
        loadConnected(id, by)
            .then((result) => {
                if (paper.entry_id === id && similarBy === by) connected = result;
            })
            .catch(() => {
                if (paper.entry_id === id && similarBy === by) connected = { papers: [], shared: new Map() };
            });
    });
    /** Number shown in a row of the Similar tab in the two citation graph ways */
    const sharedWith = (item: Paper) =>
        tab === "related" && similarBy !== "content" ? connected?.shared.get(item.entry_id) : undefined;
    const connecting = $derived(similarBy !== "content" && connected === null);

    const lists = $derived({
        cites: data?.cites ?? [],
        citedBy: data?.citedBy ?? [],
        related: similarBy === "content" ? (data?.related ?? []) : (connected?.papers ?? []),
    });

    const visible = $derived.by(() => {
        if (tab === "abstract") return [];
        const q = listFilter.trim().toLowerCase();
        const items = lists[tab].filter(
            (p) => !q || p.title.toLowerCase().includes(q) || p.authors.toLowerCase().includes(q),
        );
        if (tab === "related") return items; // keep the relevance order
        const time = (p: Paper) => (p.published ? Date.parse(p.published) : 0);
        return [...items].sort((a, b) =>
            listSort === "citations"
                ? citationCount(b) - citationCount(a)
                : listSort === "newest"
                  ? time(b) - time(a)
                  : time(a) - time(b),
        );
    });

    /** How many references and citations the dataset holds, the lists only have the most cited */
    const shownOf = $derived({ cites: data?.citesTotal ?? 0, citedBy: data?.citedByTotal ?? 0 });

    const tabs = $derived([
        { id: "abstract" as const, label: "Abstract" },
        { id: "cites" as const, label: "References", count: data?.citesTotal ?? 0 },
        { id: "citedBy" as const, label: "Citations", count: data?.citedByTotal ?? 0 },
        { id: "related" as const, label: "Similar", count: lists.related.length },
    ]);

    const emptyText: Record<Exclude<DetailsTab, "abstract">, string> = {
        cites: "None of the papers it references are in the dataset.",
        citedBy: "No paper in the dataset cites this one.",
        related: "No similar papers are known for this paper.",
    };

    async function copyBibtex() {
        try {
            await navigator.clipboard.writeText(toBibtex(full));
            copied = true;
            setTimeout(() => (copied = false), 1500);
        } catch {
            window.prompt("Copy the BibTeX entry:", toBibtex(full));
        }
    }
</script>

<aside class="details" aria-label="Paper details">
    <header>
        <div class="toolbar">
            {#if backTo}
                <Button variant="ghost" size="sm" onclick={onback} title="Back to: {backTo}">
                    <ArrowLeft /> Back
                </Button>
            {:else}
                <span></span>
            {/if}
            <div class="tools">
                {#if canLocate}
                    <Button variant="ghost" size="sm" onclick={onlocate} title="Show this paper on the map of its category">
                        <Crosshair /> Show on map
                    </Button>
                {/if}
                <Button
                    variant="ghost"
                    size="sm"
                    icon
                    label={isFavorite ? "Remove from library" : "Save to library"}
                    pressed={isFavorite}
                    onclick={onfavorite}
                >
                    <Star fill={isFavorite ? "currentColor" : "none"} />
                </Button>
                <Button variant="ghost" size="sm" icon label="Close" onclick={onclose}><X /></Button>
            </div>
        </div>

        <p class="context" style:--c={categoryColor(full.categories)}>
            <span class="cat-name">{context.categoryName || context.categoryId}</span>
            {#if context.categoryName && context.categoryName !== context.categoryId}
                <span class="ident">{context.categoryId}</span>
            {/if}
            {#if context.subjectName}<span class="dim">· {context.subjectName}</span>{/if}
        </p>

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

        <p class="meta">
            {#if full.published}<span>{formatDate(full.published)}</span>{/if}
            <span>arXiv:<span class="ident">{full.entry_id}</span></span>
            {#if full.journal_ref}<span class="journal" title={full.journal_ref}>{full.journal_ref}</span>{/if}
        </p>

        <p class="links">
            <a class="pill strong" href={links.pdf} target="_blank" rel="noopener noreferrer"><FileText /> PDF</a>
            <a class="pill" href={links.arxiv} target="_blank" rel="noopener noreferrer">arXiv <ArrowUpRight /></a>
            {#if links.doi}<a class="pill" href={links.doi} target="_blank" rel="noopener noreferrer">DOI <ArrowUpRight /></a>{/if}
            {#if links.semanticScholar}
                <a class="pill" href={links.semanticScholar} target="_blank" rel="noopener noreferrer"
                    >Semantic Scholar <ArrowUpRight /></a
                >
            {/if}
            <button class="pill" onclick={copyBibtex}>
                {#if copied}<Check /> Copied{:else}<Copy /> BibTeX{/if}
            </button>
        </p>
    </header>

    <div class="tabs" role="tablist">
        {#each tabs as t}
            <button role="tab" aria-selected={tab === t.id} class:active={tab === t.id} onclick={() => (tab = t.id)}>
                {t.label}
                {#if t.count !== undefined && data}<span class="count">{t.count.toLocaleString("en")}</span>{/if}
            </button>
        {/each}
    </div>

    <div class="content">
        {#if error}
            <p class="note">{error}</p>
        {:else if tab === "abstract"}
            {#if full.abstract}
                <p class="abstract">{full.abstract}</p>
            {:else if !data}
                <div class="loading"><Spinner /></div>
            {:else}
                <p class="note">No abstract available.</p>
            {/if}
            <dl class="facts">
                <div>
                    <dt>References</dt>
                    <dd>
                        {#if data}
                            {data.citesTotal.toLocaleString("en")} in the dataset
                            {#if data.externalCites}<small>+ {data.externalCites.toLocaleString("en")} elsewhere</small>{/if}
                        {:else}…{/if}
                    </dd>
                </div>
                <div>
                    <dt>Citations</dt>
                    <dd>
                        {#if data}
                            {data.citedByTotal.toLocaleString("en")} in the dataset
                            {#if citationCount(full) > data.citedByTotal}
                                <small>of {citationCount(full).toLocaleString("en")} known</small>
                            {/if}
                        {:else}…{/if}
                    </dd>
                </div>
                {#if categories.length}
                    <div>
                        <dt>Categories</dt>
                        <dd>
                            {#each categories as c, i}
                                <span title={subcategoryName(c)}><span class="ident">{c}</span>{i < categories.length - 1 ? ", " : ""}</span>
                            {/each}
                        </dd>
                    </div>
                {/if}
                {#if full.updated && full.updated !== full.published}
                    <div>
                        <dt>Updated</dt>
                        <dd>{formatDate(full.updated)}</dd>
                    </div>
                {/if}
                {#if full.doi}
                    <div>
                        <dt>DOI</dt>
                        <dd><a href={links.doi} target="_blank" rel="noopener noreferrer" class="ident">{full.doi}</a></dd>
                    </div>
                {/if}
            </dl>
        {:else if !data}
            <div class="loading"><Spinner /></div>
        {:else}
            {#if tab === "related"}
                <div class="segmented ways" role="tablist" aria-label="Similar by">
                    {#each [["content", "Content"], ["references", "Shared references"], ["citations", "Cited together"]] as [id, label]}
                        <button
                            role="tab"
                            aria-selected={similarBy === id}
                            class:active={similarBy === id}
                            onclick={() => (similarBy = id as SimilarBy)}>{label}</button
                        >
                    {/each}
                </div>
            {/if}
            {#if lists[tab].length > 4}
                <div class="list-tools">
                    <input class="field" placeholder="Filter by title or author" bind:value={listFilter} />
                    {#if tab !== "related"}
                        <select class="field" bind:value={listSort} aria-label="Sort">
                            <option value="citations">Most cited</option>
                            <option value="newest">Newest</option>
                            <option value="oldest">Oldest</option>
                        </select>
                    {/if}
                </div>
            {/if}
            {#if tab === "related" && connecting}
                <div class="loading"><Spinner /></div>
            {:else if tab === "related" && data}
                <p class="note">
                    {similarBy === "references"
                        ? "Papers that cite the same papers as this one (bibliographic coupling). The number is how many references they share; the order also weighs how long both reference lists are."
                        : similarBy === "citations"
                          ? "Papers that are cited together with this one (co-citation). The number is how many papers in the dataset cite both; the order also weighs how often each is cited."
                          : data.relatedBasis === "embedding"
                            ? "The papers nearest to this one in the embedding of title and abstract, nearest first."
                            : data.relatedBasis === "map"
                              ? "The papers nearest to this one on the map, nearest first. The embedding of this paper is not in the database, so this is a rough guide: same topic area, not necessarily the most similar papers."
                              : "Recommended by Semantic Scholar."}
                </p>
            {/if}
            {#if tab !== "related" && shownOf[tab] > lists[tab].length}
                <p class="note">
                    The {lists[tab].length} most cited of {shownOf[tab].toLocaleString("en")} in the dataset.
                </p>
            {/if}
            <ul class="list">
                {#each visible as item (item.entry_id)}
                    <PaperRow
                        title={item.title}
                        authors={item.authors}
                        published={item.published}
                        categories={item.categories}
                        count={sharedWith(item) ?? citationCount(item)}
                        countLabel={sharedWith(item) === undefined
                            ? "Citations"
                            : similarBy === "references"
                              ? "Shared references"
                              : "Papers citing both"}
                        onclick={() => onselect(item)}
                    />
                {:else}
                    {#if !(tab === "related" && connecting)}
                        <li class="note">
                            {listFilter
                                ? "Nothing matches the filter."
                                : tab === "related" && similarBy === "references"
                                  ? "No paper in the dataset shares two or more references with this one."
                                  : tab === "related" && similarBy === "citations"
                                    ? "No paper in the dataset is cited together with this one at least twice."
                                    : emptyText[tab]}
                        </li>
                    {/if}
                {/each}
            </ul>
        {/if}
    </div>
</aside>

<style>
    .details {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        background: var(--surface);
        border-left: 1px solid var(--border);
    }

    header {
        padding: 10px 14px 14px 20px;
    }
    .toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-left: -6px;
    }
    .tools {
        display: flex;
        gap: 2px;
        flex-shrink: 0;
    }
    .tools :global([aria-pressed="true"]) {
        color: var(--accent);
    }

    .context {
        display: flex;
        align-items: baseline;
        gap: 6px;
        min-width: 0;
        margin: 6px 0 0;
        color: var(--text-3);
        font-size: var(--text-xs);
        white-space: nowrap;
    }
    .context .cat-name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        color: color-mix(in srgb, var(--c) 72%, var(--text));
        font-weight: 600;
    }
    .context .dim {
        overflow: hidden;
        text-overflow: ellipsis;
    }

    h2 {
        margin: 10px 0 8px;
        font-size: 1.25rem;
        font-weight: 600;
        line-height: 1.3;
        letter-spacing: -0.005em;
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
        color: var(--accent);
        text-decoration: underline;
        text-underline-offset: 2px;
    }
    .author.active {
        color: var(--accent);
        font-weight: 500;
    }
    .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 2px 12px;
        margin: 6px 0 0;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .journal {
        flex-basis: 100%;
        color: var(--text-2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .links {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin: 12px 0 0;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        height: 26px;
        padding: 0 9px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        color: var(--text-2);
        font-size: var(--text-xs);
        font-weight: 500;
        text-decoration: none;
        cursor: pointer;
    }
    .pill:hover {
        border-color: var(--border-strong);
        background: var(--surface-2);
        color: var(--text);
        text-decoration: none;
    }
    .pill.strong {
        border-color: var(--accent);
        background: var(--accent);
        color: var(--accent-fg);
    }
    .pill.strong:hover {
        border-color: var(--accent-hover);
        background: var(--accent-hover);
        color: var(--accent-fg);
    }
    .pill :global(svg) {
        width: 13px;
        height: 13px;
    }

    .content {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 14px 10px 16px;
    }
    .abstract {
        margin: 0 10px 18px;
        color: var(--text);
        font-size: var(--text-base);
        line-height: 1.6;
        text-wrap: pretty;
    }
    .facts {
        display: grid;
        gap: 10px;
        margin: 0 10px;
        padding-top: 14px;
        border-top: 1px solid var(--border);
    }
    .facts div {
        display: grid;
        grid-template-columns: 90px 1fr;
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
        overflow-wrap: anywhere;
    }
    dd small {
        margin-left: 4px;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .ways {
        display: flex;
        margin: 10px 14px 0;
    }
    .ways :global(button) {
        flex: 1;
        padding: 4px 6px;
        font-size: var(--text-xs);
        white-space: nowrap;
    }
    .list-tools {
        display: flex;
        gap: 6px;
        margin: 0 6px 10px;
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
