<!--
  Dashboard.svelte

  Slide-in panel on the left side of the screen.
  Two tabs:
    • Recent (History) - automatically tracks the last 10 papers you opened
    • Favorites        - papers you explicitly starred

  Favorites can be organised into named groups:
    - Click "+ New Group" to create a group
    - Drag a paper card onto a group header to move it there
    - Click the arrows (⇄) button on a card to pick a group from a dropdown
    - Click ✕ on a group header to delete it (asks for confirmation first)

  All data is stored in the browser's localStorage so it persists across page refreshes.
-->
<script lang="ts">
    import { createEventDispatcher, onMount } from "svelte";
    import { getSubcategoryName } from "../utils/arxivTaxonomy";

    export let isOpen: boolean = false;

    const HISTORY_KEY = "monaalisa_history_v1";
    const FAVORITES_KEY = "monaalisa_favorites_v1";
    const GROUPS_KEY = "monaalisa_fav_groups_v1";
    const MAX_HISTORY = 10;
    const MAX_STR = 500; // max chars for any stored string

    interface DashboardItem {
        entry_id: string;
        title: string;
        authors: string;
        categories: string | null;
        published: string | null;
        savedAt: number;
    }

    interface FavoriteGroup {
        id: string;
        name: string;
        paperIds: string[];
    }

    const dispatch = createEventDispatcher<{
        navigate: DashboardItem;
        close: void;
    }>();

    let history: DashboardItem[] = [];
    let favorites: DashboardItem[] = [];
    let groups: FavoriteGroup[] = [];
    let activeTab: "history" | "favorites" = "history";

    // ─── group UI state ───────────────────────────────────────────
    let deleteGroupConfirmId: string | null = null;
    let newGroupNameInput = "";
    let showNewGroupInput = false;
    let expandedGroups = new Set<string>(["__ungrouped__"]);

    // ─── validation & sanitisation ────────────────────────────────────
    function clamp(s: unknown, max: number): string {
        if (typeof s !== "string") return "";
        return s.slice(0, max);
    }

    function isValidItem(obj: unknown): obj is DashboardItem {
        if (!obj || typeof obj !== "object") return false;
        const o = obj as Record<string, unknown>;
        return (
            typeof o.entry_id === "string" &&
            o.entry_id.length > 0 &&
            typeof o.title === "string" &&
            o.title.length > 0 &&
            typeof o.authors === "string" &&
            typeof o.savedAt === "number"
        );
    }

    function isValidGroup(obj: unknown): obj is FavoriteGroup {
        if (!obj || typeof obj !== "object") return false;
        const o = obj as Record<string, unknown>;
        return (
            typeof o.id === "string" &&
            o.id.length > 0 &&
            typeof o.name === "string" &&
            o.name.length > 0 &&
            Array.isArray(o.paperIds)
        );
    }

    function loadList(key: string): DashboardItem[] {
        try {
            const raw =
                typeof localStorage !== "undefined"
                    ? localStorage.getItem(key)
                    : null;
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return [];
            return parsed.filter(isValidItem).map((item) => ({
                entry_id: clamp(item.entry_id, 100),
                title: clamp(item.title, MAX_STR),
                authors: clamp(item.authors, MAX_STR),
                categories: item.categories
                    ? clamp(item.categories, 200)
                    : null,
                published: item.published ? clamp(item.published, 30) : null,
                savedAt: item.savedAt,
            }));
        } catch {
            return [];
        }
    }

    function saveList(key: string, list: DashboardItem[]) {
        try {
            if (typeof localStorage !== "undefined") {
                localStorage.setItem(key, JSON.stringify(list));
            }
        } catch {}
    }

    function loadGroups(): FavoriteGroup[] {
        try {
            const raw =
                typeof localStorage !== "undefined"
                    ? localStorage.getItem(GROUPS_KEY)
                    : null;
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return [];
            return parsed.filter(isValidGroup).map((g) => ({
                id: clamp(g.id, 50),
                name: clamp(g.name, 100),
                paperIds: (g.paperIds as unknown[])
                    .filter((id) => typeof id === "string")
                    .map((id) => clamp(id as string, 100)),
            }));
        } catch {
            return [];
        }
    }

    function saveGroups() {
        try {
            if (typeof localStorage !== "undefined") {
                localStorage.setItem(GROUPS_KEY, JSON.stringify(groups));
            }
        } catch {}
    }

    // ─── public API (called from GraphLayout) ─────────────────────────
    export function addToHistory(paper: {
        entry_id: string;
        title: string;
        authors: string;
        categories: string | null;
        published: string | null;
    }) {
        const item: DashboardItem = {
            entry_id: clamp(paper.entry_id, 100),
            title: clamp(paper.title, MAX_STR),
            authors: clamp(paper.authors, MAX_STR),
            categories: paper.categories ? clamp(paper.categories, 200) : null,
            published: paper.published ? clamp(paper.published, 30) : null,
            savedAt: Date.now(),
        };
        history = [
            item,
            ...history.filter((h) => h.entry_id !== paper.entry_id),
        ].slice(0, MAX_HISTORY);
        saveList(HISTORY_KEY, history);
    }

    /** Backward-compat: remove if favorited, or add (without group) if not */
    export function toggleFavorite(paper: {
        entry_id: string;
        title: string;
        authors: string;
        categories: string | null;
        published: string | null;
    }) {
        if (isFavorite(paper.entry_id)) {
            removeFavoriteById(paper.entry_id);
        } else {
            addFavoriteWithGroups(paper, []);
        }
    }

    export function isFavorite(entryId: string): boolean {
        return favorites.some((f) => f.entry_id === entryId);
    }

    /** Add to favorites in specified groups; create a new group if newGroupName is provided */
    export function addFavoriteWithGroups(
        paper: {
            entry_id: string;
            title: string;
            authors: string;
            categories: string | null;
            published: string | null;
        },
        groupIds: string[],
        newGroupName?: string | null,
    ) {
        let finalGroupIds = [...groupIds];
        if (newGroupName && newGroupName.trim()) {
            const newGroup: FavoriteGroup = {
                id: `grp_${Date.now()}`,
                name: clamp(newGroupName.trim(), 100),
                paperIds: [],
            };
            groups = [...groups, newGroup];
            finalGroupIds.push(newGroup.id);
            saveGroups();
        }
        const entry_id = clamp(paper.entry_id, 100);
        if (!favorites.some((f) => f.entry_id === entry_id)) {
            favorites = [
                {
                    entry_id,
                    title: clamp(paper.title, MAX_STR),
                    authors: clamp(paper.authors, MAX_STR),
                    categories: paper.categories
                        ? clamp(paper.categories, 200)
                        : null,
                    published: paper.published
                        ? clamp(paper.published, 30)
                        : null,
                    savedAt: Date.now(),
                },
                ...favorites,
            ];
            saveList(FAVORITES_KEY, favorites);
        }
        if (finalGroupIds.length > 0) {
            groups = groups.map((g) =>
                finalGroupIds.includes(g.id) && !g.paperIds.includes(entry_id)
                    ? { ...g, paperIds: [...g.paperIds, entry_id] }
                    : g,
            );
            saveGroups();
        }
    }

    /** Remove paper from favorites and all groups */
    export function removeFavoriteById(entryId: string) {
        favorites = favorites.filter((f) => f.entry_id !== entryId);
        groups = groups.map((g) => ({
            ...g,
            paperIds: g.paperIds.filter((id) => id !== entryId),
        }));
        saveList(FAVORITES_KEY, favorites);
        saveGroups();
    }

    export function getGroups(): FavoriteGroup[] {
        return groups;
    }

    // ─── helpers ──────────────────────────────────────────────────────
    function formatYear(d: string | null): string {
        if (!d) return "-";
        return new Date(d).getFullYear().toString();
    }

    function formatFirstCat(cats: string | null): string {
        if (!cats) return "";
        const cat = cats.trim().split(/[\s,]+/)[0] ?? "";
        if (!cat) return "";
        const full = getSubcategoryName(cat);
        return full !== cat ? `${full} (${cat})` : cat;
    }

    function truncate(s: string, n: number): string {
        return s.length > n ? s.slice(0, n) + "…" : s;
    }

    function removeHistory(entryId: string) {
        history = history.filter((h) => h.entry_id !== entryId);
        saveList(HISTORY_KEY, history);
    }

    function removeFavorite(entryId: string) {
        removeFavoriteById(entryId);
    }

    function clearHistory() {
        history = [];
        saveList(HISTORY_KEY, history);
    }

    // ─── group management ────────────────────────────────────────────────────
    function createGroup(name: string) {
        const trimmed = name.trim();
        if (
            !trimmed ||
            groups.some((g) => g.name.toLowerCase() === trimmed.toLowerCase())
        )
            return;
        const newGroup: FavoriteGroup = {
            id: `grp_${Date.now()}`,
            name: clamp(trimmed, 100),
            paperIds: [],
        };
        groups = [...groups, newGroup];
        saveGroups();
        expandedGroups.add(newGroup.id);
        expandedGroups = new Set(expandedGroups);
        newGroupNameInput = "";
        showNewGroupInput = false;
    }

    function deleteGroup(groupId: string) {
        groups = groups.filter((g) => g.id !== groupId);
        saveGroups();
        deleteGroupConfirmId = null;
    }

    function removePaperFromGroup(entryId: string, groupId: string) {
        groups = groups.map((g) =>
            g.id === groupId
                ? { ...g, paperIds: g.paperIds.filter((id) => id !== entryId) }
                : g,
        );
        saveGroups();
    }

    function toggleGroupExpanded(groupId: string) {
        if (expandedGroups.has(groupId)) expandedGroups.delete(groupId);
        else expandedGroups.add(groupId);
        expandedGroups = new Set(expandedGroups);
    }

    // ─── drag-and-drop state ─────────────────────────────────────────────────
    // Tracks which paper is currently being dragged and where it came from
    let draggingEntryId: string | null = null;
    let draggingFromGroupId: string | null = null; // null = came from Ungrouped
    let dropTargetGroupId: string | null = null; // null = no active drop target

    /**
     * Called when the user starts dragging a favorite paper card.
     * @param entryId - the paper's unique ID
     * @param fromGroupId - which group it belongs to, or null if ungrouped
     */
    function onDragStart(entryId: string, fromGroupId: string | null) {
        draggingEntryId = entryId;
        draggingFromGroupId = fromGroupId;
    }

    /** Called while the dragged card is hovering over a group drop zone */
    function onDragOverGroup(targetGroupId: string | null) {
        dropTargetGroupId = targetGroupId;
    }

    /** Called when the card is released over a group drop zone */
    function onDropToGroup(targetGroupId: string | null) {
        if (!draggingEntryId) return;
        const from = draggingFromGroupId;
        const to = targetGroupId;
        if (from !== to) {
            // Remove from source named group (if it was in one)
            if (from) {
                groups = groups.map((g) =>
                    g.id === from
                        ? {
                              ...g,
                              paperIds: g.paperIds.filter(
                                  (id) => id !== draggingEntryId,
                              ),
                          }
                        : g,
                );
            }
            // Add to target named group (if one was specified)
            if (to) {
                groups = groups.map((g) =>
                    g.id === to && !g.paperIds.includes(draggingEntryId!)
                        ? { ...g, paperIds: [...g.paperIds, draggingEntryId!] }
                        : g,
                );
            }
            saveGroups();
        }
        draggingEntryId = null;
        draggingFromGroupId = null;
        dropTargetGroupId = null;
    }

    /** Clean up drag state if the drag is cancelled */
    function onDragEnd() {
        draggingEntryId = null;
        draggingFromGroupId = null;
        dropTargetGroupId = null;
    }

    // ─── "Move to group" dropdown ─────────────────────────────────────────────
    // moveMenuOpenId: which paper's move-menu is currently open
    let moveMenuOpenId: string | null = null;
    let moveMenuFromGroupId: string | null = null;

    /**
     * Move a paper from one group (or ungrouped) to another.
     * @param entryId - paper to move
     * @param toGroupId - destination group ID, or null to move to "Ungrouped"
     * @param fromGroupId - source group ID, or null if currently ungrouped
     */
    function moveToGroup(
        entryId: string,
        toGroupId: string | null,
        fromGroupId: string | null,
    ) {
        if (toGroupId === fromGroupId) {
            moveMenuOpenId = null;
            return;
        }
        if (fromGroupId) {
            groups = groups.map((g) =>
                g.id === fromGroupId
                    ? {
                          ...g,
                          paperIds: g.paperIds.filter((id) => id !== entryId),
                      }
                    : g,
            );
        }
        if (toGroupId) {
            groups = groups.map((g) =>
                g.id === toGroupId && !g.paperIds.includes(entryId)
                    ? { ...g, paperIds: [...g.paperIds, entryId] }
                    : g,
            );
        }
        saveGroups();
        moveMenuOpenId = null;
    }

    // ─── computed ───────────────────────────────────────────────────────────
    $: ungroupedFavorites = favorites.filter(
        (f) => !groups.some((g) => g.paperIds.includes(f.entry_id)),
    );

    onMount(() => {
        history = loadList(HISTORY_KEY);
        favorites = loadList(FAVORITES_KEY);
        groups = loadGroups();
    });
</script>

<!-- overlay backdrop -->
{#if isOpen}
    <div
        class="db-backdrop"
        on:click={() => dispatch("close")}
        on:keydown={() => {}}
        role="presentation"
    ></div>
{/if}

<div class="dashboard" class:open={isOpen}>
    <!-- header -->
    <div class="db-header">
        <div class="db-title-row">
            <span class="db-icon">&#9733;</span>
            <h2 class="db-title">Dashboard</h2>
        </div>
        <button
            class="db-close"
            on:click={() => dispatch("close")}
            title="Close">&#x2715;</button
        >
    </div>

    <!-- tabs -->
    <div class="db-tabs">
        <button
            class="db-tab"
            class:active={activeTab === "history"}
            on:click={() => {
                activeTab = "history";
            }}
        >
            Recent ({history.length})
        </button>
        <button
            class="db-tab"
            class:active={activeTab === "favorites"}
            on:click={() => {
                activeTab = "favorites";
            }}
        >
            Favorites ({favorites.length})
        </button>
    </div>

    <!-- tab content - clicking anywhere in the content area closes any open move-to menus -->
    <div
        class="db-content"
        on:click={() => {
            if (moveMenuOpenId) moveMenuOpenId = null;
        }}
    >
        <!-- ── history tab ── -->
        {#if activeTab === "history"}
            {#if history.length === 0}
                <p class="db-empty">
                    No papers viewed yet. Open a paper to start tracking
                    history.
                </p>
            {:else}
                <div class="db-actions-row">
                    <button class="db-clear-btn" on:click={clearHistory}
                        >Clear all</button
                    >
                </div>
                {#each history as item (item.entry_id)}
                    <div class="db-item">
                        <div class="db-item-body">
                            <button
                                class="db-item-title"
                                on:click={() => dispatch("navigate", item)}
                            >
                                {truncate(item.title, 90)}
                            </button>
                            <p class="db-item-meta">
                                {truncate(item.authors, 60)}
                            </p>
                            <p class="db-item-meta db-item-tags">
                                {formatYear(item.published)}
                                {#if item.categories}&nbsp;·&nbsp;{formatFirstCat(
                                        item.categories,
                                    )}{/if}
                            </p>
                        </div>
                        <button
                            class="db-del-btn"
                            title="Remove from history"
                            on:click={() => removeHistory(item.entry_id)}
                            >&#x2715;</button
                        >
                    </div>
                {/each}
            {/if}

            <!-- ── favorites tab ── -->
        {:else if favorites.length === 0}
            <p class="db-empty">
                No favorites yet. Star a paper from the detail view to save it
                here.
            </p>
        {:else}
            <!-- New Group button / inline input row -->
            <div class="db-actions-row">
                {#if showNewGroupInput}
                    <div class="db-new-group-row">
                        <input
                            class="db-new-group-input"
                            type="text"
                            placeholder="Group name…"
                            bind:value={newGroupNameInput}
                            on:keydown={(e) => {
                                if (e.key === "Enter")
                                    createGroup(newGroupNameInput);
                                else if (e.key === "Escape") {
                                    showNewGroupInput = false;
                                    newGroupNameInput = "";
                                }
                            }}
                        />
                        <button
                            class="db-new-group-ok"
                            on:click={() => createGroup(newGroupNameInput)}
                            >Add</button
                        >
                        <button
                            class="db-new-group-cancel"
                            on:click={() => {
                                showNewGroupInput = false;
                                newGroupNameInput = "";
                            }}>&#x2715;</button
                        >
                    </div>
                {:else}
                    <button
                        class="db-add-group-btn"
                        on:click={() => {
                            showNewGroupInput = true;
                        }}>+ New Group</button
                    >
                {/if}
            </div>

            <!-- Named groups - shown even when empty so users can drag papers into them -->
            {#each groups as group (group.id)}
                {@const groupPapers = group.paperIds
                    .map((id) => favorites.find((f) => f.entry_id === id))
                    .filter(Boolean) as typeof favorites}
                <!-- svelte-ignore a11y-no-static-element-interactions -->
                <div
                    class="db-group"
                    class:drag-over={dropTargetGroupId === group.id}
                    on:dragover|preventDefault={() => onDragOverGroup(group.id)}
                    on:dragleave={() => {
                        if (dropTargetGroupId === group.id)
                            dropTargetGroupId = null;
                    }}
                    on:drop={() => onDropToGroup(group.id)}
                >
                    <!-- Group header: click to expand/collapse, drag target -->
                    <!-- svelte-ignore a11y-interactive-supports-focus -->
                    <div
                        class="db-group-header"
                        on:click={() => toggleGroupExpanded(group.id)}
                        on:keydown={() => {}}
                        role="button"
                        tabindex="0"
                    >
                        <span class="db-group-arrow"
                            >{expandedGroups.has(group.id) ? "▾" : "▸"}</span
                        >
                        <!-- Name turns blue (active-tab colour) when the group is open -->
                        <span
                            class="db-group-name"
                            class:expanded={expandedGroups.has(group.id)}
                            >{group.name}</span
                        >
                        <span class="db-group-count"
                            >({groupPapers.length})</span
                        >
                        {#if deleteGroupConfirmId === group.id}
                            <!-- Inline "are you sure?" before actually deleting -->
                            <span class="db-group-confirm-del">
                                Delete?
                                <button
                                    class="db-group-del-yes"
                                    on:click|stopPropagation={() =>
                                        deleteGroup(group.id)}>Yes</button
                                >
                                <button
                                    class="db-group-del-no"
                                    on:click|stopPropagation={() => {
                                        deleteGroupConfirmId = null;
                                    }}>No</button
                                >
                            </span>
                        {:else}
                            <button
                                class="db-group-del-btn"
                                title="Delete group"
                                on:click|stopPropagation={() => {
                                    deleteGroupConfirmId = group.id;
                                }}>&#x2715;</button
                            >
                        {/if}
                    </div>

                    {#if expandedGroups.has(group.id)}
                        {#if groupPapers.length === 0}
                            <!-- Empty group placeholder - also a drag target -->
                            <p class="db-group-empty">
                                Drag a paper here to add it to this group.
                            </p>
                        {/if}
                        {#each groupPapers as item (item.entry_id)}
                            <!-- Each paper is draggable. On dragstart we record where it came from. -->
                            <!-- svelte-ignore a11y-no-static-element-interactions -->
                            <div
                                class="db-item db-item-grouped"
                                class:dragging={draggingEntryId ===
                                    item.entry_id}
                                draggable="true"
                                on:dragstart={() =>
                                    onDragStart(item.entry_id, group.id)}
                                on:dragend={onDragEnd}
                            >
                                <div class="db-item-body">
                                    <button
                                        class="db-item-title"
                                        on:click={() =>
                                            dispatch("navigate", item)}
                                    >
                                        {truncate(item.title, 90)}
                                    </button>
                                    <p class="db-item-meta">
                                        {truncate(item.authors, 60)}
                                    </p>
                                    <p class="db-item-meta db-item-tags">
                                        {formatYear(item.published)}
                                        {#if item.categories}&nbsp;·&nbsp;{formatFirstCat(
                                                item.categories,
                                            )}{/if}
                                    </p>
                                </div>
                                <div class="db-item-actions">
                                    <!-- Move to another group dropdown -->
                                    <div class="db-move-wrap">
                                        <button
                                            class="db-move-btn"
                                            title="Move to group"
                                            on:click|stopPropagation={() => {
                                                moveMenuOpenId =
                                                    moveMenuOpenId ===
                                                    item.entry_id
                                                        ? null
                                                        : item.entry_id;
                                                moveMenuFromGroupId = group.id;
                                            }}>&#x21C4;</button
                                        >
                                        {#if moveMenuOpenId === item.entry_id}
                                            <!-- svelte-ignore a11y-no-static-element-interactions -->
                                            <div
                                                class="db-move-menu"
                                                on:click|stopPropagation={() => {}}
                                            >
                                                {#each groups.filter((g) => g.id !== group.id) as tg (tg.id)}
                                                    <button
                                                        class="db-move-option"
                                                        on:click={() =>
                                                            moveToGroup(
                                                                item.entry_id,
                                                                tg.id,
                                                                group.id,
                                                            )}
                                                    >
                                                        {tg.name}
                                                    </button>
                                                {/each}
                                                <!-- Move to Ungrouped = remove from this group -->
                                                <button
                                                    class="db-move-option db-move-ungroup"
                                                    on:click={() =>
                                                        moveToGroup(
                                                            item.entry_id,
                                                            null,
                                                            group.id,
                                                        )}
                                                >
                                                    Ungrouped
                                                </button>
                                            </div>
                                        {/if}
                                    </div>
                                    <!-- Remove from group (paper stays as ungrouped favorite) -->
                                    <button
                                        class="db-del-btn"
                                        title="Remove from group"
                                        on:click={() =>
                                            removePaperFromGroup(
                                                item.entry_id,
                                                group.id,
                                            )}>&#x2715;</button
                                    >
                                    <!-- Remove from favorites entirely -->
                                    <button
                                        class="db-del-btn db-del-fav"
                                        title="Remove from favorites"
                                        on:click={() =>
                                            removeFavorite(item.entry_id)}
                                        >&#9733;</button
                                    >
                                </div>
                            </div>
                        {/each}
                    {/if}
                </div>
            {/each}

            <!-- Ungrouped section - papers not in any named group -->
            {#if ungroupedFavorites.length > 0 || groups.length > 0}
                <!-- svelte-ignore a11y-no-static-element-interactions -->
                <div
                    class="db-group"
                    class:drag-over={dropTargetGroupId === "__ungrouped__"}
                    on:dragover|preventDefault={() =>
                        onDragOverGroup("__ungrouped__")}
                    on:dragleave={() => {
                        if (dropTargetGroupId === "__ungrouped__")
                            dropTargetGroupId = null;
                    }}
                    on:drop={() => onDropToGroup(null)}
                >
                    <!-- svelte-ignore a11y-interactive-supports-focus -->
                    <div
                        class="db-group-header"
                        on:click={() => toggleGroupExpanded("__ungrouped__")}
                        on:keydown={() => {}}
                        role="button"
                        tabindex="0"
                    >
                        <span class="db-group-arrow"
                            >{expandedGroups.has("__ungrouped__")
                                ? "▾"
                                : "▸"}</span
                        >
                        <!-- Same blue-on-expand behaviour as named groups -->
                        <span
                            class="db-group-name"
                            class:expanded={expandedGroups.has("__ungrouped__")}
                            >Ungrouped</span
                        >
                        <span class="db-group-count"
                            >({ungroupedFavorites.length})</span
                        >
                    </div>
                    {#if expandedGroups.has("__ungrouped__")}
                        {#if ungroupedFavorites.length === 0}
                            <p class="db-group-empty">
                                All favorites are in groups.
                            </p>
                        {/if}
                        {#each ungroupedFavorites as item (item.entry_id)}
                            <!-- svelte-ignore a11y-no-static-element-interactions -->
                            <div
                                class="db-item db-item-grouped"
                                class:dragging={draggingEntryId ===
                                    item.entry_id}
                                draggable="true"
                                on:dragstart={() =>
                                    onDragStart(item.entry_id, null)}
                                on:dragend={onDragEnd}
                            >
                                <div class="db-item-body">
                                    <button
                                        class="db-item-title"
                                        on:click={() =>
                                            dispatch("navigate", item)}
                                    >
                                        {truncate(item.title, 90)}
                                    </button>
                                    <p class="db-item-meta">
                                        {truncate(item.authors, 60)}
                                    </p>
                                    <p class="db-item-meta db-item-tags">
                                        {formatYear(item.published)}
                                        {#if item.categories}&nbsp;·&nbsp;{formatFirstCat(
                                                item.categories,
                                            )}{/if}
                                    </p>
                                </div>
                                <div class="db-item-actions">
                                    <!-- Move to a named group dropdown -->
                                    {#if groups.length > 0}
                                        <div class="db-move-wrap">
                                            <button
                                                class="db-move-btn"
                                                title="Move to group"
                                                on:click|stopPropagation={() => {
                                                    moveMenuOpenId =
                                                        moveMenuOpenId ===
                                                        item.entry_id
                                                            ? null
                                                            : item.entry_id;
                                                    moveMenuFromGroupId = null;
                                                }}>&#x21C4;</button
                                            >
                                            {#if moveMenuOpenId === item.entry_id}
                                                <!-- svelte-ignore a11y-no-static-element-interactions -->
                                                <div
                                                    class="db-move-menu"
                                                    on:click|stopPropagation={() => {}}
                                                >
                                                    {#each groups as tg (tg.id)}
                                                        <button
                                                            class="db-move-option"
                                                            on:click={() =>
                                                                moveToGroup(
                                                                    item.entry_id,
                                                                    tg.id,
                                                                    null,
                                                                )}
                                                        >
                                                            {tg.name}
                                                        </button>
                                                    {/each}
                                                </div>
                                            {/if}
                                        </div>
                                    {/if}
                                    <!-- Remove from favorites entirely -->
                                    <button
                                        class="db-del-btn db-del-fav"
                                        title="Remove from favorites"
                                        on:click={() =>
                                            removeFavorite(item.entry_id)}
                                        >&#9733;</button
                                    >
                                </div>
                            </div>
                        {/each}
                    {/if}
                </div>
            {/if}
        {/if}
    </div>
</div>

<style>
    .db-backdrop {
        position: fixed;
        inset: 0;
        z-index: 199;
        background: rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(2px);
    }

    .dashboard {
        position: fixed;
        top: 0;
        left: 0;
        width: 360px;
        height: 100vh;
        z-index: 200;
        display: flex;
        flex-direction: column;
        background: var(--bg-secondary, #141530);
        border-right: 1px solid var(--glass-border, rgba(255, 255, 255, 0.1));
        box-shadow: 4px 0 32px rgba(0, 0, 0, 0.5);
        transform: translateX(-100%);
        transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }

    .dashboard.open {
        transform: translateX(0);
    }

    /* ── header ── */
    .db-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 16px 10px;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        flex-shrink: 0;
        background: var(--bg-secondary, #141530);
    }

    .db-title-row {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .db-icon {
        font-size: 16px;
        color: var(--accent-yellow, #ffd166);
    }

    .db-title {
        margin: 0;
        font-size: 15px;
        font-weight: 700;
        color: var(--text-primary, #f0f0f8);
        letter-spacing: 0.3px;
    }

    .db-close {
        background: none;
        border: 1px solid transparent;
        color: var(--text-muted, #6b6b8d);
        font-size: 14px;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: var(--radius-sm, 8px);
        transition: all 0.15s ease;
        line-height: 1;
    }
    .db-close:hover {
        color: var(--text-primary, #f0f0f8);
        background: rgba(255, 255, 255, 0.07);
        border-color: rgba(255, 255, 255, 0.12);
    }

    /* ── tabs ── */
    .db-tabs {
        display: flex;
        gap: 0;
        border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
        flex-shrink: 0;
    }

    .db-tab {
        flex: 1;
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 10px 12px;
        color: var(--text-muted, #6b6b8d);
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .db-tab:hover {
        color: var(--text-primary, #f0f0f8);
        background: rgba(255, 255, 255, 0.04);
    }
    .db-tab.active {
        color: var(--accent-cyan, #22d3ee);
        border-bottom-color: var(--accent-cyan, #22d3ee);
    }

    /* ── content ── */
    .db-content {
        flex: 1;
        overflow-y: auto;
        padding: 8px 0;
        scrollbar-width: thin;
        scrollbar-color: rgba(147, 51, 234, 0.3) transparent;
    }
    .db-content::-webkit-scrollbar {
        width: 4px;
    }
    .db-content::-webkit-scrollbar-track {
        background: transparent;
    }
    .db-content::-webkit-scrollbar-thumb {
        background: rgba(147, 51, 234, 0.3);
        border-radius: 99px;
    }

    .db-empty {
        margin: 32px 20px;
        font-size: 12px;
        color: var(--text-muted, #6b6b8d);
        line-height: 1.6;
        text-align: center;
    }

    .db-actions-row {
        display: flex;
        justify-content: flex-end;
        padding: 4px 14px 6px;
    }

    .db-clear-btn {
        background: none;
        border: 1px solid rgba(245, 101, 101, 0.25);
        color: #f56565;
        font-size: 11px;
        padding: 3px 10px;
        border-radius: 999px;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .db-clear-btn:hover {
        background: rgba(245, 101, 101, 0.12);
        border-color: rgba(245, 101, 101, 0.45);
    }

    /* ── item ── */
    .db-item {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 9px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        transition: background 0.12s ease;
    }
    .db-item:hover {
        background: rgba(255, 255, 255, 0.03);
    }

    .db-item-body {
        flex: 1;
        min-width: 0;
    }

    .db-item-title {
        background: none;
        border: none;
        padding: 0;
        margin: 0 0 4px;
        color: var(--text-primary, #f0f0f8);
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        text-align: left;
        line-height: 1.4;
        transition: color 0.12s ease;
        white-space: normal;
        word-break: break-word;
    }
    .db-item-title:hover {
        color: var(--accent-cyan, #22d3ee);
    }

    .db-item-meta {
        margin: 0;
        font-size: 11px;
        color: var(--text-muted, #6b6b8d);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .db-item-tags {
        color: var(--text-secondary, #a8a8c8);
        font-size: 10.5px;
        margin-top: 2px;
    }

    .db-del-btn {
        background: none;
        border: 1px solid transparent;
        color: var(--text-muted, #6b6b8d);
        font-size: 12px;
        cursor: pointer;
        padding: 3px 6px;
        border-radius: var(--radius-sm, 8px);
        transition: all 0.12s ease;
        flex-shrink: 0;
        margin-top: 1px;
        line-height: 1;
    }
    .db-del-btn:hover {
        color: #f56565;
        background: rgba(245, 101, 101, 0.1);
        border-color: rgba(245, 101, 101, 0.25);
    }

    .db-del-fav {
        color: var(--accent-yellow, #ffd166);
        opacity: 0.6;
    }
    .db-del-fav:hover {
        color: #f56565;
        background: rgba(245, 101, 101, 0.1);
        border-color: rgba(245, 101, 101, 0.25);
        opacity: 1;
    }

    /* ── groups ── */
    .db-add-group-btn {
        background: none;
        border: 1px solid rgba(99, 179, 237, 0.25);
        color: var(--accent-cyan, #22d3ee);
        font-size: 11px;
        padding: 3px 10px;
        border-radius: 999px;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .db-add-group-btn:hover {
        background: rgba(99, 179, 237, 0.1);
        border-color: rgba(99, 179, 237, 0.45);
    }

    .db-new-group-row {
        display: flex;
        align-items: center;
        gap: 5px;
        width: 100%;
    }

    .db-new-group-input {
        flex: 1;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.14);
        color: var(--text-primary, #f0f0f8);
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 6px;
        outline: none;
        min-width: 0;
    }
    .db-new-group-input:focus {
        border-color: var(--accent-cyan, #22d3ee);
    }

    .db-new-group-ok {
        background: rgba(34, 211, 238, 0.15);
        border: 1px solid rgba(34, 211, 238, 0.35);
        color: var(--accent-cyan, #22d3ee);
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 6px;
        cursor: pointer;
    }
    .db-new-group-cancel {
        background: none;
        border: 1px solid transparent;
        color: var(--text-muted, #6b6b8d);
        font-size: 11px;
        padding: 3px 6px;
        border-radius: 6px;
        cursor: pointer;
    }

    .db-group {
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .db-group-header {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 7px 12px;
        cursor: pointer;
        background: rgba(255, 255, 255, 0.025);
        user-select: none;
        transition: background 0.12s;
    }
    .db-group-header:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    .db-group-arrow {
        font-size: 10px;
        color: var(--text-muted, #6b6b8d);
        flex-shrink: 0;
    }

    .db-group-name {
        font-size: 11.5px;
        font-weight: 600;
        color: var(--text-secondary, #a8a8c8);
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        transition: color 0.15s ease;
    }

    /* When the group is expanded, use the active-tab accent colour (cyan) */
    .db-group-name.expanded {
        color: var(--accent-cyan, #22d3ee);
    }

    .db-group-count {
        font-size: 10px;
        color: var(--text-muted, #6b6b8d);
        flex-shrink: 0;
    }

    /* Styled like Sidebar's close-btn but scaled down to fit the group header */
    .db-group-del-btn {
        background: none;
        border: none;
        color: var(--text-muted, #6b6b8d);
        font-size: 14px;
        cursor: pointer;
        padding: 0;
        width: 18px;
        height: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        transition: all 0.15s ease;
        flex-shrink: 0;
        margin-left: auto;
    }
    .db-group-del-btn:hover {
        color: var(--text-primary, #f0f0f8);
        background: rgba(147, 51, 234, 0.15);
    }

    .db-group-confirm-del {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 10.5px;
        color: #f56565;
        flex-shrink: 0;
    }

    .db-group-del-yes,
    .db-group-del-no {
        font-size: 10px;
        padding: 1px 6px;
        border-radius: 4px;
        cursor: pointer;
        border: 1px solid;
    }
    .db-group-del-yes {
        background: rgba(245, 101, 101, 0.18);
        border-color: rgba(245, 101, 101, 0.4);
        color: #f56565;
    }
    .db-group-del-no {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(255, 255, 255, 0.15);
        color: var(--text-muted, #6b6b8d);
    }

    .db-item-grouped {
        padding-left: 24px;
    }

    .db-item-actions {
        display: flex;
        flex-direction: column;
        gap: 2px;
        flex-shrink: 0;
    }

    /* ── drag and drop ── */
    /* Highlight a group when a card is dragged over it */
    .db-group.drag-over > .db-group-header {
        background: rgba(34, 211, 238, 0.12);
        border-left: 2px solid var(--accent-cyan, #22d3ee);
    }
    /* Make the dragged card semi-transparent while being moved */
    .db-item.dragging {
        opacity: 0.4;
    }
    /* Short dashed help text inside an empty group drop zone */
    .db-group-empty {
        font-size: 10.5px;
        color: var(--text-muted, #6b6b8d);
        text-align: center;
        padding: 6px 12px;
        border: 1px dashed rgba(255, 255, 255, 0.08);
        margin: 4px 10px;
        border-radius: 6px;
    }

    /* ── move-to-group button and dropdown ── */
    .db-move-wrap {
        position: relative;
    }

    .db-move-btn {
        background: none;
        border: 1px solid transparent;
        color: var(--text-muted, #6b6b8d);
        font-size: 12px;
        cursor: pointer;
        padding: 3px 6px;
        border-radius: var(--radius-sm, 8px);
        transition: all 0.12s ease;
        line-height: 1;
    }
    .db-move-btn:hover {
        color: var(--accent-cyan, #22d3ee);
        background: rgba(34, 211, 238, 0.08);
        border-color: rgba(34, 211, 238, 0.25);
    }

    /* Dropdown that appears on move-btn click */
    .db-move-menu {
        position: absolute;
        right: 0;
        top: 100%;
        z-index: 300;
        background: var(--bg-secondary, #141530);
        border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.12));
        border-radius: 8px;
        min-width: 130px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }

    .db-move-option {
        background: none;
        border: none;
        color: var(--text-primary, #f0f0f8);
        font-size: 11px;
        text-align: left;
        padding: 6px 10px;
        cursor: pointer;
        transition: background 0.1s;
        white-space: nowrap;
    }
    .db-move-option:hover {
        background: rgba(255, 255, 255, 0.07);
    }
    .db-move-ungroup {
        color: var(--text-muted, #6b6b8d);
        border-top: 1px solid rgba(255, 255, 255, 0.07);
    }
</style>
