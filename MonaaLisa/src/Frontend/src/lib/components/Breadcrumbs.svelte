<script module lang="ts">
    export interface Crumb {
        label: string;
        /** Missing for the current (last) crumb */
        onclick?: () => void;
    }
</script>

<script lang="ts">
    import { ChevronRight } from "@lucide/svelte";

    let { crumbs }: { crumbs: Crumb[] } = $props();
</script>

<nav aria-label="Breadcrumb">
    <ol>
        {#each crumbs as crumb, i}
            <li>
                {#if i > 0}<ChevronRight class="sep" aria-hidden="true" />{/if}
                {#if crumb.onclick && i < crumbs.length - 1}
                    <button onclick={crumb.onclick}>{crumb.label}</button>
                {:else}
                    <span aria-current="page" title={crumb.label}>{crumb.label}</span>
                {/if}
            </li>
        {/each}
    </ol>
</nav>

<style>
    ol {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 2px 0;
        margin: 0;
        padding: 0;
        list-style: none;
    }
    li {
        display: flex;
        align-items: center;
        min-width: 0;
        max-width: 100%;
    }
    li :global(.sep) {
        width: 12px;
        height: 12px;
        margin: 0 2px;
        color: var(--text-3);
        flex-shrink: 0;
    }
    button,
    span {
        padding: 2px 4px;
        border: 0;
        border-radius: var(--radius-sm);
        background: none;
        font-size: var(--text-xs);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    button {
        color: var(--text-3);
        cursor: pointer;
    }
    button:hover {
        background: var(--surface-2);
        color: var(--text);
    }
    span {
        color: var(--text-2);
        max-width: 300px;
    }
</style>
