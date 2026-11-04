<!--
  Asks before loading a very large number of papers or graph nodes.
  Confirm unlocks after a short countdown so the warning is actually read.
-->
<script lang="ts">
    import Dialog from "$lib/components/ui/Dialog.svelte";
    import Button from "$lib/components/ui/Button.svelte";

    interface Props {
        /** The limit the user picked, null when the dialog is closed. 0 means "all". */
        limit: number | null;
        onconfirm: () => void;
        oncancel: () => void;
    }

    let { limit, onconfirm, oncancel }: Props = $props();

    const COUNTDOWN_SECONDS = 3;
    let secondsLeft = $state(COUNTDOWN_SECONDS);

    $effect(() => {
        if (limit === null) return;
        secondsLeft = COUNTDOWN_SECONDS;
        const timer = setInterval(() => {
            secondsLeft -= 1;
            if (secondsLeft <= 0) clearInterval(timer);
        }, 1000);
        return () => clearInterval(timer);
    });

    const amount = $derived(limit === 0 ? "all papers" : `${limit?.toLocaleString("en")} items`);
</script>

<Dialog open={limit !== null} onclose={oncancel} title="Load {amount}?" role="alertdialog">
    <p>
        Drawing this many points can take a while and may make the page slow or unresponsive on older devices. You can
        go back to a smaller limit at any time.
    </p>

    {#snippet footer()}
        <Button variant="ghost" onclick={oncancel}>Cancel</Button>
        <Button variant="primary" disabled={secondsLeft > 0} onclick={onconfirm}>
            {secondsLeft > 0 ? `Load anyway (${secondsLeft})` : "Load anyway"}
        </Button>
    {/snippet}
</Dialog>

<style>
    p {
        margin: 0;
        line-height: 1.6;
    }
</style>
