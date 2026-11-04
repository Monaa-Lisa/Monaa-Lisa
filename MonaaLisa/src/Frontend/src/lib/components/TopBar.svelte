<!--
  The single bar at the top of the app: brand, breadcrumb path of the current
  view, and the view's controls on the right (passed in as `actions`).
-->
<script module lang="ts">
    export interface Crumb {
        label: string;
        /** Missing for the current (last) crumb */
        onclick?: () => void;
    }
</script>

<script lang="ts">
    import type { Snippet } from "svelte";
    import { ChevronRight } from "@lucide/svelte";

    interface Props {
        crumbs: Crumb[];
        onhome: () => void;
        actions?: Snippet;
    }

    let { crumbs, onhome, actions }: Props = $props();
</script>

<header class="topbar">
    <button class="brand" onclick={onhome} title="Back to all categories">
        <span class="mark" aria-hidden="true">ML</span>
        <span class="name">Monaa-Lisa</span>
    </button>

    <nav class="crumbs" aria-label="Breadcrumb">
        <ol>
            {#each crumbs as crumb, i}
                <li>
                    {#if i > 0}<ChevronRight class="sep" aria-hidden="true" />{/if}
                    {#if crumb.onclick && i < crumbs.length - 1}
                        <button class="crumb" onclick={crumb.onclick}>{crumb.label}</button>
                    {:else}
                        <span class="crumb current" aria-current="page" title={crumb.label}>{crumb.label}</span>
                    {/if}
                </li>
            {/each}
        </ol>
    </nav>

    <div class="actions">
        {@render actions?.()}
    </div>
</header>

<style>
    .topbar {
        display: flex;
        align-items: center;
        gap: 16px;
        height: var(--topbar-height);
        padding: 0 12px 0 16px;
        border-bottom: 1px solid var(--border);
        background: var(--surface);
        flex-shrink: 0;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 4px 8px 4px 0;
        border: 0;
        background: none;
        cursor: pointer;
    }
    .mark {
        display: grid;
        place-items: center;
        width: 24px;
        height: 24px;
        border-radius: var(--radius-sm);
        background: var(--accent);
        color: var(--accent-fg);
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.02em;
    }
    .name {
        font-size: var(--text-base);
        font-weight: 600;
        color: var(--text);
    }

    .crumbs {
        flex: 1;
        min-width: 0;
        padding-left: 16px;
        border-left: 1px solid var(--border);
    }
    ol {
        display: flex;
        align-items: center;
        margin: 0;
        padding: 0;
        list-style: none;
        min-width: 0;
    }
    li {
        display: flex;
        align-items: center;
        min-width: 0;
    }
    li:last-child {
        flex-shrink: 1;
    }
    li :global(.sep) {
        width: 14px;
        height: 14px;
        margin: 0 4px;
        color: var(--text-3);
        flex-shrink: 0;
    }
    .crumb {
        padding: 4px 6px;
        border: 0;
        border-radius: var(--radius-sm);
        background: none;
        color: var(--text-2);
        font-size: var(--text-sm);
        white-space: nowrap;
        cursor: pointer;
    }
    button.crumb:hover {
        background: var(--surface-2);
        color: var(--text);
    }
    .crumb.current {
        color: var(--text);
        cursor: default;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 60ch;
    }

    .actions {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
    }
</style>
