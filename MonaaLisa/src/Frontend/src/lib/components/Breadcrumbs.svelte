<script module lang="ts">
    export interface Crumb {
        label: string;
        /** Missing for the current (last) crumb */
        onclick?: () => void;
    }
</script>

<script lang="ts">
    let { crumbs }: { crumbs: Crumb[] } = $props();
</script>

<nav aria-label="Breadcrumb">
    <ol>
        {#each crumbs as crumb, i}
            <li>
                {#if i > 0}<span class="sep" aria-hidden="true">/</span>{/if}
                {#if crumb.onclick && i < crumbs.length - 1}
                    <button onclick={crumb.onclick}>{crumb.label}</button>
                {:else}
                    <span class="current" aria-current="page" title={crumb.label}>{crumb.label}</span>
                {/if}
            </li>
        {/each}
    </ol>
</nav>

<style>
    ol {
        display: flex;
        align-items: center;
        min-width: 0;
        margin: 0;
        padding: 0;
        list-style: none;
    }
    li {
        display: flex;
        align-items: center;
        min-width: 0;
    }
    .sep {
        margin: 0 6px;
        color: var(--border-strong);
    }
    button,
    .current {
        padding: 2px 0;
        border: 0;
        background: none;
        font-size: var(--text-sm);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    button {
        color: var(--text-2);
        cursor: pointer;
    }
    button:hover {
        color: var(--accent);
        text-decoration: underline;
        text-underline-offset: 2px;
    }
    .current {
        color: var(--text);
        font-weight: 500;
        max-width: 420px;
    }
</style>
