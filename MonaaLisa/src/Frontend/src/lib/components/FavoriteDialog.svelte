<!--
  Adds a paper to the favorites, optionally into existing groups or a new one.
-->
<script lang="ts">
    import Dialog from "$lib/components/ui/Dialog.svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import type { Paper } from "$lib/types/paper";

    interface Group {
        id: string;
        name: string;
    }

    interface Props {
        /** The paper to add, null when the dialog is closed */
        paper: Paper | null;
        groups: Group[];
        onsave: (groupIds: string[], newGroupName: string | null) => void;
        oncancel: () => void;
    }

    let { paper, groups, onsave, oncancel }: Props = $props();

    let selected = $state<string[]>([]);
    let newGroupName = $state("");

    // start empty every time the dialog opens for a paper
    $effect(() => {
        if (paper) {
            selected = [];
            newGroupName = "";
        }
    });

    function save() {
        onsave(selected, newGroupName.trim() || null);
    }
</script>

<Dialog open={paper !== null} onclose={oncancel} title="Add to favorites">
    {#if paper}
        <p class="paper-title">{paper.title}</p>
    {/if}

    {#if groups.length > 0}
        <fieldset>
            <legend>Groups</legend>
            {#each groups as group (group.id)}
                <label class="group">
                    <input type="checkbox" value={group.id} bind:group={selected} />
                    {group.name}
                </label>
            {/each}
        </fieldset>
    {/if}

    <label class="new-group">
        <span>New group (optional)</span>
        <input
            class="field"
            type="text"
            placeholder="e.g. Thesis related work"
            bind:value={newGroupName}
            onkeydown={(e) => e.key === "Enter" && save()}
        />
    </label>

    {#snippet footer()}
        <Button variant="ghost" onclick={oncancel}>Cancel</Button>
        <Button variant="primary" onclick={save}>Add to favorites</Button>
    {/snippet}
</Dialog>

<style>
    .paper-title {
        margin: 0 0 16px;
        color: var(--text);
        font-weight: 500;
        line-height: 1.4;
    }
    fieldset {
        margin: 0 0 16px;
        padding: 0;
        border: 0;
        display: grid;
        gap: 6px;
    }
    legend {
        margin-bottom: 6px;
        color: var(--text-3);
        font-size: var(--text-xs);
        font-weight: 500;
    }
    .group {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--text);
        cursor: pointer;
    }
    .new-group {
        display: grid;
        gap: 6px;
    }
    .new-group span {
        color: var(--text-3);
        font-size: var(--text-xs);
        font-weight: 500;
    }
</style>
