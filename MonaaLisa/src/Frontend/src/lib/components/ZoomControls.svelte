<script lang="ts">
    import { Maximize, Minus, Plus } from "@lucide/svelte";

    interface Props {
        onzoomin: () => void;
        onzoomout: () => void;
        onreset: () => void;
    }

    let { onzoomin, onzoomout, onreset }: Props = $props();
</script>

<div class="zoom" role="group" aria-label="Zoom">
    <button onclick={onzoomin} aria-label="Zoom in" title="Zoom in"><Plus /></button>
    <button onclick={onzoomout} aria-label="Zoom out" title="Zoom out"><Minus /></button>
    <button onclick={onreset} aria-label="Fit to view" title="Fit to view"><Maximize /></button>
</div>

<style>
    .zoom {
        position: absolute;
        right: 12px;
        bottom: 12px;
        display: flex;
        flex-direction: column;
        border: 1px solid var(--border-strong);
        border-radius: var(--radius);
        background: var(--surface);
        overflow: hidden;
    }
    button {
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        border: 0;
        background: none;
        color: var(--text-2);
        cursor: pointer;
    }
    button + button {
        border-top: 1px solid var(--border);
    }
    button:hover {
        background: var(--surface-2);
        color: var(--text);
    }
    button :global(svg) {
        width: 14px;
        height: 14px;
    }
</style>
