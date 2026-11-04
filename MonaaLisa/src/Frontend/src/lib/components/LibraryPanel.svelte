<!--
  Library: saved papers grouped by the user, and recently opened papers.
  The saved papers can be exported as a BibTeX file.
-->
<script lang="ts">
    import { Download, Plus, X } from "@lucide/svelte";
    import Button from "$lib/components/ui/Button.svelte";
    import PaperRow from "$lib/components/PaperRow.svelte";
    import { library, type LibraryItem } from "$lib/library.svelte";
    import { getPapersByIds } from "$lib/api";
    import { toBibtex, toPapers } from "$lib/paper";

    interface Props {
        onopen: (entryId: string) => void;
        onclose: () => void;
    }

    let { onopen, onclose }: Props = $props();

    let tab = $state<"recent" | "favorites">("favorites");
    let newGroupName = $state("");
    let addingGroup = $state(false);
    let exporting = $state(false);

    const sections = $derived.by(() => {
        const grouped = library.groups.map((g) => ({
            id: g.id as string | null,
            name: g.name,
            items: library.favorites.filter((f) => g.paperIds.includes(f.entry_id)),
        }));
        const ungrouped = library.favorites.filter((f) => !library.groupOf(f.entry_id));
        return [...grouped, { id: null, name: "Not in a group", items: ungrouped }].filter(
            (s) => s.id !== null || s.items.length > 0,
        );
    });

    function addGroup() {
        if (newGroupName.trim()) library.createGroup(newGroupName);
        newGroupName = "";
        addingGroup = false;
    }

    /** Downloads all saved papers as one .bib file, with the full records from the API */
    async function exportBibtex() {
        exporting = true;
        try {
            const full = toPapers(await getPapersByIds(library.favorites.map((f) => f.entry_id)));
            const byId = new Map(full.map((p) => [p.entry_id, p]));
            const entries = library.favorites.map((f) => {
                const paper = byId.get(f.entry_id);
                return paper
                    ? toBibtex(paper)
                    : `@misc{arxiv${f.entry_id.replace(/\W/g, "")},\n  title = {${f.title}},\n  eprint = {${f.entry_id}},\n  archivePrefix = {arXiv}\n}`;
            });
            const blob = new Blob([entries.join("\n\n") + "\n"], { type: "application/x-bibtex" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "monaa-lisa-library.bib";
            a.click();
            URL.revokeObjectURL(url);
        } finally {
            exporting = false;
        }
    }
</script>

{#snippet favoriteActions(item: LibraryItem)}
    {#if library.groups.length}
        <select
            class="field move"
            aria-label="Move to group"
            value={library.groupOf(item.entry_id) ?? ""}
            onchange={(e) => library.moveToGroup(item.entry_id, e.currentTarget.value || null)}
        >
            <option value="">No group</option>
            {#each library.groups as g (g.id)}
                <option value={g.id}>{g.name}</option>
            {/each}
        </select>
    {/if}
    <Button variant="ghost" size="sm" icon label="Remove from library" onclick={() => library.removeFavorite(item.entry_id)}>
        <X />
    </Button>
{/snippet}

<aside class="library" aria-label="Library">
    <header>
        <h2>Library</h2>
        <Button variant="ghost" size="sm" icon label="Close library" onclick={onclose}><X /></Button>
    </header>

    <div class="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "favorites"} class:active={tab === "favorites"} onclick={() => (tab = "favorites")}>
            Saved <span class="count">{library.favorites.length}</span>
        </button>
        <button role="tab" aria-selected={tab === "recent"} class:active={tab === "recent"} onclick={() => (tab = "recent")}>
            Recently opened <span class="count">{library.history.length}</span>
        </button>
    </div>

    <div class="content">
        {#if tab === "recent"}
            {#if library.history.length}
                <ul class="list">
                    {#each library.history as item (item.entry_id)}
                        <PaperRow title={item.title} authors={item.authors} published={item.published} categories={item.categories} onclick={() => onopen(item.entry_id)}>
                            {#snippet actions()}
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    icon
                                    label="Remove from recent"
                                    onclick={() => library.removeFromHistory(item.entry_id)}><X /></Button
                                >
                            {/snippet}
                        </PaperRow>
                    {/each}
                </ul>
                <div class="footer">
                    <Button variant="ghost" size="sm" onclick={() => library.clearHistory()}>Clear list</Button>
                </div>
            {:else}
                <p class="empty">Papers you open appear here.</p>
            {/if}
        {:else}
            {#if library.favorites.length === 0}
                <p class="empty">Use the star in a paper's details to save it here. Saved papers stay in this browser.</p>
            {/if}
            {#each sections as section (section.id ?? "none")}
                <section>
                    <div class="section-head">
                        <h3>{section.name}</h3>
                        {#if section.id}
                            <Button
                                variant="ghost"
                                size="sm"
                                icon
                                label="Delete group {section.name}"
                                onclick={() => section.id && library.deleteGroup(section.id)}><X /></Button
                            >
                        {/if}
                    </div>
                    {#if section.items.length}
                        <ul class="list">
                            {#each section.items as item (item.entry_id)}
                                <PaperRow title={item.title} authors={item.authors} published={item.published} categories={item.categories} onclick={() => onopen(item.entry_id)}>
                                    {#snippet actions()}{@render favoriteActions(item)}{/snippet}
                                </PaperRow>
                            {/each}
                        </ul>
                    {:else}
                        <p class="empty small">No papers in this group yet.</p>
                    {/if}
                </section>
            {/each}
            <div class="footer">
                {#if addingGroup}
                    <input
                        class="field"
                        placeholder="Group name"
                        bind:value={newGroupName}
                        onkeydown={(e) => {
                            if (e.key === "Enter") addGroup();
                            if (e.key === "Escape") addingGroup = false;
                        }}
                    />
                    <Button size="sm" onclick={addGroup}>Add</Button>
                {:else}
                    <Button variant="ghost" size="sm" onclick={() => (addingGroup = true)}><Plus /> New group</Button>
                    {#if library.favorites.length}
                        <Button variant="ghost" size="sm" disabled={exporting} onclick={exportBibtex}>
                            <Download /> Export BibTeX
                        </Button>
                    {/if}
                {/if}
            </div>
        {/if}
    </div>
</aside>

<style>
    .library {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        background: var(--surface);
        border-left: 1px solid var(--border);
    }
    header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 14px 6px 20px;
    }
    h2 {
        margin: 0;
        font-size: var(--text-md);
        font-weight: 600;
    }
    .content {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 8px 0;
    }
    section + section {
        margin-top: 12px;
    }
    .section-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 10px 6px 20px;
    }
    h3 {
        margin: 0;
        color: var(--text-2);
        font-size: var(--text-xs);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .list {
        margin: 0;
        padding: 0;
        list-style: none;
    }
    .move {
        height: 24px;
        max-width: 130px;
        font-size: var(--text-xs);
    }
    .empty {
        margin: 12px 16px;
        color: var(--text-3);
        font-size: var(--text-sm);
    }
    .empty.small {
        margin: 2px 16px 8px;
        font-size: var(--text-xs);
    }
    .footer {
        display: flex;
        gap: 6px;
        padding: 12px 12px 4px;
    }
    .footer .field {
        flex: 1;
    }
</style>
