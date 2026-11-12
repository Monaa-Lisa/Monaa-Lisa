<!--
  Map of categories as packed circles: every circle is one category, its
  area is proportional to the number of papers. Used for the subject level
  and the category level. Plain buttons, so the circles are keyboard
  reachable and the text can be selected.
-->
<script lang="ts">
    import { packCircles } from "$lib/bubbles";
    import { formatCount } from "$lib/categories";
    import type { CategoryNode } from "$lib/types/paper";

    interface Props {
        items: CategoryNode[];
        color: (item: CategoryNode) => string;
        /** Show the category id (e.g. hep-th) as well as the name */
        showIds?: boolean;
        /** What the counts are, e.g. "papers in the dataset" */
        unit?: string;
        onselect: (item: CategoryNode) => void;
    }

    let { items, color, showIds = false, unit = "papers", onselect }: Props = $props();

    const PADDING = 32;
    let width = $state(0);
    let height = $state(0);

    const packed = $derived(packCircles(items, (i) => i.count, Math.max(1, (width || 1) / (height || 1))));

    // scale the packing to the available area
    const layout = $derived.by(() => {
        if (!packed.length || !width || !height) return [];
        const minX = Math.min(...packed.map((b) => b.x - b.r));
        const maxX = Math.max(...packed.map((b) => b.x + b.r));
        const minY = Math.min(...packed.map((b) => b.y - b.r));
        const maxY = Math.max(...packed.map((b) => b.y + b.r));
        const scale = Math.min((width - 2 * PADDING) / (maxX - minX), (height - 2 * PADDING) / (maxY - minY));
        const offsetX = width / 2 - ((minX + maxX) / 2) * scale;
        const offsetY = height / 2 - ((minY + maxY) / 2) * scale;
        return packed.map((b) => ({
            item: b.item,
            cx: b.x * scale + offsetX,
            cy: b.y * scale + offsetY,
            r: b.r * scale,
        }));
    });

    /** Name text size that fits the circle, between 10 and 18 px */
    function nameSize(r: number): number {
        return Math.max(10, Math.min(18, r * 0.24));
    }
</script>

<div class="bubbles" bind:clientWidth={width} bind:clientHeight={height}>
    {#each layout as bubble (bubble.item.id)}
        <button
            class="bubble"
            style:left="{bubble.cx - bubble.r}px"
            style:top="{bubble.cy - bubble.r}px"
            style:width="{bubble.r * 2}px"
            style:height="{bubble.r * 2}px"
            style:padding="{bubble.r * 0.14}px"
            style:--c={color(bubble.item)}
            title="{bubble.item.name} · {bubble.item.count.toLocaleString('en')} {unit}"
            onclick={() => onselect(bubble.item)}
        >
            <span class="name" style:font-size="{nameSize(bubble.r)}px">{bubble.item.name}</span>
            {#if bubble.r >= 46}
                <span class="count">{formatCount(bubble.item.count)} papers</span>
                {#if showIds && bubble.r >= 62}<span class="id">{bubble.item.id}</span>{/if}
            {/if}
        </button>
    {/each}
</div>

<style>
    .bubbles {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
    }
    .bubble {
        position: absolute;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
        border: 1px solid color-mix(in srgb, var(--c) 55%, var(--bg));
        border-radius: 50%;
        background: color-mix(in srgb, var(--c) 20%, var(--surface));
        color: var(--text);
        text-align: center;
        overflow: hidden;
        cursor: pointer;
        transition:
            background var(--duration) var(--ease),
            border-color var(--duration) var(--ease);
    }
    .bubble:hover,
    .bubble:focus-visible {
        background: color-mix(in srgb, var(--c) 30%, var(--bg));
        border-color: color-mix(in srgb, var(--c) 85%, var(--text));
        z-index: 1;
    }
    .name {
        display: -webkit-box;
        -webkit-line-clamp: 3;
        line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        font-weight: 500;
        line-height: 1.2;
        text-wrap: balance;
    }
    .count {
        color: var(--text-2);
        font-size: var(--text-xs);
    }
    .id {
        color: var(--text-3);
        font-variant-numeric: tabular-nums;
        font-size: var(--text-xs);
    }
</style>
