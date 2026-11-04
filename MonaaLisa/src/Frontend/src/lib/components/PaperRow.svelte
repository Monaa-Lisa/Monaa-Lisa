<!--
  One paper in a list: title, authors, year and primary category.
  Used by the search results, the inspector lists and the library.
-->
<script lang="ts">
    import type { Snippet } from "svelte";
    import { categoryColor } from "$lib/categories";
    import { primaryCategory, publishedYear, shortAuthors } from "$lib/paper";

    interface Props {
        title: string;
        authors: string;
        published: string | null;
        categories: string | null;
        /** Optional number on the right, e.g. citation count */
        count?: number;
        countLabel?: string;
        active?: boolean;
        onclick: () => void;
        /** Extra controls shown on hover, e.g. a remove button */
        actions?: Snippet;
    }

    let { title, authors, published, categories, count, countLabel, active = false, onclick, actions }: Props =
        $props();

    const category = $derived(primaryCategory(categories));
    const year = $derived(publishedYear(published));
</script>

<li class="row" class:active>
    <button class="main" {onclick}>
        <span class="title">{title}</span>
        <span class="meta">
            {#if category}
                <span class="cat"><i style:background={categoryColor(categories)}></i>{category}</span>
            {/if}
            {#if year}<span>{year}</span>{/if}
            {#if authors}<span class="authors">{shortAuthors(authors, 2)}</span>{/if}
        </span>
    </button>
    {#if count !== undefined}
        <span class="count" title={countLabel}>{count.toLocaleString("en")}</span>
    {/if}
    {#if actions}
        <span class="actions">{@render actions()}</span>
    {/if}
</li>

<style>
    .row {
        position: relative;
        display: flex;
        align-items: flex-start;
        gap: 8px;
        border-radius: var(--radius);
    }
    .row:hover,
    .row.active {
        background: var(--surface-2);
    }
    .main {
        display: grid;
        gap: 3px;
        flex: 1;
        min-width: 0;
        padding: 8px 10px;
        border: 0;
        background: none;
        text-align: left;
        cursor: pointer;
    }
    .title {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        color: var(--text);
        font-size: var(--text-sm);
        font-weight: 500;
        line-height: 1.35;
    }
    .meta {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        color: var(--text-3);
        font-size: var(--text-xs);
    }
    .cat {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-family: var(--font-mono);
        flex-shrink: 0;
    }
    .cat i {
        width: 6px;
        height: 6px;
        border-radius: 50%;
    }
    .authors {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .count {
        padding: 9px 10px 0 0;
        color: var(--text-2);
        font-family: var(--font-mono);
        font-size: var(--text-xs);
    }
    .actions {
        position: absolute;
        top: 6px;
        right: 6px;
        display: none;
        gap: 2px;
        padding: 2px;
        border-radius: var(--radius);
        background: var(--surface-3);
    }
    .row:hover .actions,
    .row:focus-within .actions {
        display: flex;
    }
</style>
