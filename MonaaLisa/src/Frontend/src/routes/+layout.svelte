<script lang="ts">
    // Global design tokens (colours, radii, shadows) and scrollbar styles
    import "../app.css";

    let { children } = $props();
</script>

{@render children()}
