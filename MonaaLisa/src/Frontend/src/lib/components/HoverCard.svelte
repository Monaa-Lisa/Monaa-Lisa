<!--
  Small card that follows the pointer over a map node: title, authors, year
  and citations, plus an optional note on how the paper relates to the
  selected one.
-->
<script lang="ts">
    import { citationCount, publishedYear, shortAuthors } from "$lib/paper";
    import { paperContext } from "$lib/categories";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        paper: Paper;
        /** Pointer position inside the map, in px */
        x: number;
        y: number;
        /** Width of the map, to keep the card inside */
        width: number;
        note?: string;
    }

    let { paper, x, y, width, note }: Props = $props();

    const CARD = 320;
    const left = $derived(x + 16 + CARD > width ? Math.max(8, x - 16 - CARD) : x + 16);
    const context = $derived(paperContext(paper.categories));
</script>

<div class="hover-card" style:left="{left}px" style:top="{y + 16}px" style:width="{CARD}px" role="tooltip">
    {#if note}<span class="note">{note}</span>{/if}
    <strong>{paper.title}</strong>
    <span class="meta">
        {shortAuthors(paper.authors)}{publishedYear(paper.published) ? ` · ${publishedYear(paper.published)}` : ""}
    </span>
    <span class="meta">
        <span class="ident">{context.categoryId}</span>
        {#if context.categoryName && context.categoryName !== context.categoryId}· {context.categoryName}{/if}
        · {citationCount(paper).toLocaleString("en")} citations
    </span>
</div>

<style>
    .hover-card {
        position: absolute;
        z-index: 5;
        display: grid;
        gap: 3px;
        padding: 8px 10px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        box-shadow: var(--shadow-pop);
        pointer-events: none;
    }
    .note {
        color: var(--accent);
        font-size: var(--text-xs);
        font-weight: 500;
    }
    strong {
        color: var(--text);
        font-size: var(--text-sm);
        font-weight: 500;
        line-height: 1.35;
    }
    .meta {
        color: var(--text-2);
        font-size: var(--text-xs);
    }
</style>
