<!--
  Modal dialog on the native <dialog> element: focus trap, Escape to close
  and the backdrop come from the browser. Clicking the backdrop closes it too.
-->
<script lang="ts">
    import type { Snippet } from "svelte";
    import { X } from "@lucide/svelte";

    interface Props {
        open: boolean;
        title: string;
        onclose: () => void;
        /** Width of the dialog in px */
        width?: number;
        /** alertdialog for warnings that need a decision */
        role?: "dialog" | "alertdialog";
        children: Snippet;
        footer?: Snippet;
    }

    let { open, title, onclose, width = 440, role = "dialog", children, footer }: Props = $props();

    let dialog: HTMLDialogElement;

    $effect(() => {
        if (open && !dialog.open) dialog.showModal();
        if (!open && dialog.open) dialog.close();
    });

    function onBackdropClick(event: MouseEvent) {
        if (event.target === dialog) onclose();
    }
</script>

<dialog
    bind:this={dialog}
    {role}
    aria-labelledby="dialog-title"
    style:width="{width}px"
    onclose={onclose}
    onclick={onBackdropClick}
>
    <header>
        <h2 id="dialog-title">{title}</h2>
        <button class="close" aria-label="Close" onclick={onclose}><X /></button>
    </header>
    <div class="body">
        {@render children()}
    </div>
    {#if footer}
        <footer>{@render footer()}</footer>
    {/if}
</dialog>

<style>
    dialog {
        max-width: calc(100vw - 32px);
        max-height: calc(100vh - 64px);
        padding: 0;
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        background: var(--surface);
        color: var(--text);
        box-shadow: var(--shadow-pop);
    }
    dialog::backdrop {
        background: rgba(0, 0, 0, 0.6);
    }
    header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 16px 0 20px;
    }
    h2 {
        margin: 0;
        font-size: var(--text-md);
        font-weight: 600;
    }
    .close {
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        border: 0;
        border-radius: var(--radius);
        background: transparent;
        color: var(--text-3);
        cursor: pointer;
    }
    .close:hover {
        background: var(--surface-2);
        color: var(--text);
    }
    .close :global(svg) {
        width: 16px;
        height: 16px;
    }
    .body {
        padding: 12px 20px 20px;
        color: var(--text-2);
        font-size: var(--text-base);
        overflow-y: auto;
    }
    footer {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        padding: 12px 20px;
        border-top: 1px solid var(--border);
    }
</style>
