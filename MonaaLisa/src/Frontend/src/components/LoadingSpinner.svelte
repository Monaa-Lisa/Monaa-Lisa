<!--
  LoadingSpinner.svelte
  A simple rotating CSS ring spinner.
  Use <LoadingSpinner size={40}/> anywhere a loading indicator is needed.
-->
<script lang="ts">
    /** Diameter of the spinner in pixels. Controls overall size. */
    export let size: number = 40;
</script>

<!-- Single div - all animation is done in CSS, no JS needed -->
<div
    class="spinner"
    role="status"
    aria-label="Loading"
    style="--sz: {size}px;"
></div>

<style>
    /* Ring spinner: a circle with a brighter top-edge that rotates.
     - will-change: transform    → hints the browser to promote this element
                                   to its own GPU compositor layer before the
                                   animation starts, so it stays smooth even
                                   while the JS main thread is busay.
     - @keyframes uses explicit from/to with the same transform function so
       the browser can interpolate as a pure rotation without decomposing
       into a matrix (which would require main-thread involvement).
  */
    .spinner {
        width: var(--sz);
        height: var(--sz);
        border: calc(var(--sz) * 0.11) solid rgba(147, 51, 234, 0.2);
        border-top-color: var(--accent-purple, #9333ea);
        border-radius: 50%;
        animation: spin 0.75s linear infinite;
        flex-shrink: 0;
        will-change: transform;
    }

    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }
</style>
