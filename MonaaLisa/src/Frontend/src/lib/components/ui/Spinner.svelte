<script lang="ts">
    import { LoaderCircle } from "@lucide/svelte";

    let { size = 20, label = "Loading" }: { size?: number; label?: string } = $props();
</script>

<span class="spinner" role="status" aria-label={label} style:width="{size}px" style:height="{size}px">
    <LoaderCircle size={size} />
</span>

<style>
    .spinner {
        display: inline-grid;
        place-items: center;
        color: var(--text-3);
        animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
</style>
