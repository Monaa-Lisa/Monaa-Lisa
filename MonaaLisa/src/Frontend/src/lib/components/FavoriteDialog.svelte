<!--
  Adds a paper to the favorites, optionally into a group (existing or new).
-->
<script lang="ts">
    import Dialog from "$lib/components/ui/Dialog.svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import type { FavoriteGroup } from "$lib/library.svelte";
    import type { Paper } from "$lib/types/paper";

    interface Props {
        /** The paper to add, null when the dialog is closed */
        paper: Paper | null;
        groups: FavoriteGroup[];
        onsave: (groupId: string | null, newGroupName: string | null) => void;
        oncancel: () => void;
    }

    let { paper, groups, onsave, oncancel }: Props = $props();

    const NEW = "__new__";
    let choice = $state("");
    let newGroupName = $state("");

    // start fresh every time the dialog opens for a paper
    $effect(() => {
        if (paper) {
            choice = "";
            newGroupName = "";
        }
    });

    function save() {
        if (choice === NEW) onsave(null, newGroupName.trim() || null);
        else onsave(choice || null, null);
    }
</script>

<Dialog open={paper !== null} onclose={oncancel} title="Save to library">
    {#if paper}
        <p class="paper-title">{paper.title}</p>
    {/if}

    <label class="row">
        <span class="label">Group</span>
        <select class="field" bind:value={choice}>
            <option value="">No group</option>
            {#each groups as group (group.id)}
                <option value={group.id}>{group.name}</option>
            {/each}
            <option value={NEW}>New group…</option>
        </select>
    </label>

    {#if choice === NEW}
        <label class="row">
            <span class="label">Name</span>
            <input
                class="field"
                placeholder="e.g. Related work for my thesis"
                bind:value={newGroupName}
                onkeydown={(e) => e.key === "Enter" && save()}
            />
        </label>
    {/if}

    {#snippet footer()}
        <Button variant="ghost" onclick={oncancel}>Cancel</Button>
        <Button variant="primary" onclick={save}>Save</Button>
    {/snippet}
</Dialog>

<style>
    .paper-title {
        margin: 0 0 16px;
        color: var(--text);
        font-weight: 500;
        line-height: 1.4;
    }
    .row {
        display: grid;
        gap: 6px;
        margin-bottom: 12px;
    }
    .row .field {
        width: 100%;
    }
</style>
