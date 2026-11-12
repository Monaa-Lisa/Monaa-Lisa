/**
 * The user's library: recently opened papers and favorites (optionally in
 * named groups). Everything lives in localStorage, under the same keys the
 * old Dashboard used, so existing favorites are kept.
 */
const HISTORY_KEY = "monaalisa_history_v1";
const FAVORITES_KEY = "monaalisa_favorites_v1";
const GROUPS_KEY = "monaalisa_fav_groups_v1";
const MAX_HISTORY = 20;
const MAX_STR = 500;

export interface LibraryItem {
    entry_id: string;
    title: string;
    authors: string;
    categories: string | null;
    published: string | null;
    savedAt: number;
}

export interface FavoriteGroup {
    id: string;
    name: string;
    paperIds: string[];
}

type PaperLike = Pick<LibraryItem, "entry_id" | "title" | "authors" | "categories" | "published">;

function clamp(value: unknown, max: number): string {
    return typeof value === "string" ? value.slice(0, max) : "";
}

function toItem(paper: PaperLike, savedAt = Date.now()): LibraryItem {
    return {
        entry_id: clamp(paper.entry_id, 100),
        title: clamp(paper.title, MAX_STR),
        authors: clamp(paper.authors, MAX_STR),
        categories: paper.categories ? clamp(paper.categories, 200) : null,
        published: paper.published ? clamp(paper.published, 30) : null,
        savedAt,
    };
}

function read(key: string): unknown[] {
    try {
        const parsed = JSON.parse(localStorage.getItem(key) ?? "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function write(key: string, value: unknown) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch {
        // storage full or blocked (private mode): the library just is not saved
    }
}

function readItems(key: string): LibraryItem[] {
    return read(key)
        .filter((o): o is LibraryItem => {
            const item = o as Partial<LibraryItem>;
            return typeof item?.entry_id === "string" && !!item.entry_id && typeof item.title === "string";
        })
        .map((item) => toItem(item, typeof item.savedAt === "number" ? item.savedAt : Date.now()));
}

function readGroups(): FavoriteGroup[] {
    return read(GROUPS_KEY)
        .filter((o): o is FavoriteGroup => {
            const g = o as Partial<FavoriteGroup>;
            return typeof g?.id === "string" && typeof g.name === "string" && Array.isArray(g.paperIds);
        })
        .map((g) => ({
            id: clamp(g.id, 50),
            name: clamp(g.name, 100),
            paperIds: g.paperIds.filter((id) => typeof id === "string").map((id) => clamp(id, 100)),
        }));
}

class Library {
    history = $state<LibraryItem[]>([]);
    favorites = $state<LibraryItem[]>([]);
    groups = $state<FavoriteGroup[]>([]);

    /** Reads the stored library, call once in the browser */
    load() {
        this.history = readItems(HISTORY_KEY);
        this.favorites = readItems(FAVORITES_KEY);
        this.groups = readGroups();
    }

    addToHistory(paper: PaperLike) {
        this.history = [toItem(paper), ...this.history.filter((h) => h.entry_id !== paper.entry_id)].slice(
            0,
            MAX_HISTORY,
        );
        write(HISTORY_KEY, this.history);
    }

    removeFromHistory(entryId: string) {
        this.history = this.history.filter((h) => h.entry_id !== entryId);
        write(HISTORY_KEY, this.history);
    }

    clearHistory() {
        this.history = [];
        write(HISTORY_KEY, this.history);
    }

    isFavorite(entryId: string): boolean {
        return this.favorites.some((f) => f.entry_id === entryId);
    }

    addFavorite(paper: PaperLike, groupIds: string[] = [], newGroupName: string | null = null) {
        const targets = [...groupIds];
        if (newGroupName?.trim()) targets.push(this.createGroup(newGroupName));
        if (!this.isFavorite(paper.entry_id)) {
            this.favorites = [toItem(paper), ...this.favorites];
            write(FAVORITES_KEY, this.favorites);
        }
        for (const id of targets) this.moveToGroup(paper.entry_id, id);
    }

    removeFavorite(entryId: string) {
        this.favorites = this.favorites.filter((f) => f.entry_id !== entryId);
        this.groups = this.groups.map((g) => ({ ...g, paperIds: g.paperIds.filter((id) => id !== entryId) }));
        write(FAVORITES_KEY, this.favorites);
        write(GROUPS_KEY, this.groups);
    }

    /** Creates a group (or returns the existing one with that name) and gives back its id */
    createGroup(name: string): string {
        const trimmed = clamp(name.trim(), 100);
        const existing = this.groups.find((g) => g.name.toLowerCase() === trimmed.toLowerCase());
        if (existing) return existing.id;
        const group = { id: `grp_${Date.now()}`, name: trimmed, paperIds: [] };
        this.groups = [...this.groups, group];
        write(GROUPS_KEY, this.groups);
        return group.id;
    }

    deleteGroup(groupId: string) {
        this.groups = this.groups.filter((g) => g.id !== groupId);
        write(GROUPS_KEY, this.groups);
    }

    groupOf(entryId: string): string | null {
        return this.groups.find((g) => g.paperIds.includes(entryId))?.id ?? null;
    }

    /** Puts a favorite into one group (null = no group) */
    moveToGroup(entryId: string, groupId: string | null) {
        this.groups = this.groups.map((g) => {
            const without = g.paperIds.filter((id) => id !== entryId);
            return { ...g, paperIds: g.id === groupId ? [...without, entryId] : without };
        });
        write(GROUPS_KEY, this.groups);
    }
}

export const library = new Library();
