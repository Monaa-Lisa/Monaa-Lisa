<!--
  Treemap of categories: every tile is one category, its area is proportional
  to the number of papers. Used for the subject level and the subcategory
  level. Plain buttons, so the tiles are keyboard reachable and the text can
  be selected.
-->
<script lang="ts">
    import { squarify } from "$lib/treemap";
    import { formatCount } from "$lib/categories";
    import type { CategoryNode } from "$lib/types/paper";

    interface Props {
        items: CategoryNode[];
        color: (item: CategoryNode) => string;
        /** Show the category id (e.g. hep-th) as well as the name */
        showIds?: boolean;
        onselect: (item: CategoryNode) => void;
    }

    let { items, color, showIds = false, onselect }: Props = $props();

    const GAP = 3;
    let width = $state(0);
    let height = $state(0);

    const tiles = $derived(squarify(items, (i) => i.count, width, height));

    function sizeClass(w: number, h: number): string {
        if (w < 64 || h < 30) return "tiny";
        if (w < 120 || h < 48) return "small";
        if (w * h > 90_000) return "large";
        return "";
    }
</script>

<div class="treemap" bind:clientWidth={width} bind:clientHeight={height}>
    {#each tiles as tile (tile.item.id)}
        {@const size = sizeClass(tile.width, tile.height)}
        <button
            class="tile {size}"
            style:left="{tile.x + GAP / 2}px"
            style:top="{tile.y + GAP / 2}px"
            style:width="{Math.max(tile.width - GAP, 0)}px"
            style:height="{Math.max(tile.height - GAP, 0)}px"
            style:--c={color(tile.item)}
            title="{tile.item.name} · {tile.item.count.toLocaleString('en')} papers on arXiv"
            onclick={() => onselect(tile.item)}
        >
            {#if size !== "tiny"}
                <span class="name">{tile.item.name}</span>
                {#if size !== "small"}
                    <span class="count">{formatCount(tile.item.count)} papers</span>
                    {#if showIds}<span class="id">{tile.item.id}</span>{/if}
                {/if}
            {/if}
        </button>
    {/each}
</div>

<style>
    .treemap {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
    }
    .tile {
        position: absolute;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
        padding: 8px 10px;
        border: 1px solid color-mix(in srgb, var(--c) 45%, var(--bg));
        border-radius: var(--radius-sm);
        background: color-mix(in srgb, var(--c) 16%, var(--bg));
        color: var(--text);
        text-align: left;
        overflow: hidden;
        cursor: pointer;
        transition: background var(--duration) var(--ease);
    }
    .tile:hover,
    .tile:focus-visible {
        background: color-mix(in srgb, var(--c) 30%, var(--bg));
        border-color: color-mix(in srgb, var(--c) 80%, var(--text));
        z-index: 1;
    }
    .name {
        width: 100%;
        font-size: var(--text-sm);
        font-weight: 500;
        line-height: 1.3;
        text-wrap: balance;
    }
    .count {
        color: var(--text-2);
        font-size: var(--text-xs);
    }
    .id {
        margin-top: auto;
        color: var(--text-3);
        font-family: var(--font-mono);
        font-size: var(--text-xs);
    }
    .tile.large .name {
        font-size: var(--text-lg);
    }
    .tile.large .count {
        font-size: var(--text-sm);
    }
    .tile.small {
        padding: 5px 7px;
    }
    .tile.small .name {
        font-size: var(--text-xs);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
</style>
