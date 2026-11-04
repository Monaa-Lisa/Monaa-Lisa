import type { ApiPaper, Paper } from "$lib/types/paper";

/**
 * Reads the UMAP position from the `tsne` field. Old rows can hold it as a
 * JSON string instead of an object, both are accepted.
 */
export function parseCoordinates(tsne: unknown): [number, number] {
    let value = tsne;
    if (typeof value === "string") {
        try {
            value = JSON.parse(value);
        } catch {
            return [0, 0];
        }
    }
    if (value && typeof value === "object") {
        const { x, y } = value as { x?: unknown; y?: unknown };
        if (typeof x === "number" && typeof y === "number") return [x, y];
    }
    return [0, 0];
}

/** Turns the different shapes of id lists the API used over time into string[]. */
export function toIdList(value: unknown): string[] {
    if (Array.isArray(value)) {
        return value
            .map((item) => {
                if (typeof item === "string") return item;
                if (typeof item === "number") return String(item);
                if (item && typeof item === "object" && "entry_id" in item) {
                    return String((item as { entry_id: unknown }).entry_id ?? "");
                }
                return "";
            })
            .filter(Boolean);
    }
    if (typeof value === "string") {
        return value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
    }
    return [];
}

function authorsToString(authors: ApiPaper["authors"]): string {
    if (!authors) return "";
    return Array.isArray(authors) ? authors.join(", ") : authors;
}

/** Converts a paper from the API into the shape the components work with. */
export function toPaper(raw: ApiPaper): Paper | null {
    if (!raw?.entry_id || !raw?.title) return null;
    const [x, y] = parseCoordinates(raw.tsne);
    return {
        id: Number(raw.id ?? 0),
        entry_id: raw.entry_id,
        title: raw.title,
        authors: authorsToString(raw.authors),
        abstract: raw.abstract ?? "",
        published: raw.published ?? null,
        categories: raw.categories ?? null,
        url: raw.url ?? null,
        citations: toIdList(raw.citations),
        references: toIdList(raw.references),
        non_arxiv_citation_count: raw.non_arxiv_citation_count ?? 0,
        non_arxiv_reference_count: raw.non_arxiv_reference_count ?? 0,
        tsne1: x,
        tsne2: y,
        cluster: raw.categories ?? "U",
    };
}

export function toPapers(items: ApiPaper[]): Paper[] {
    return items.map(toPaper).filter((p): p is Paper => p !== null);
}

/** First (primary) category of a paper, e.g. "cs.LG". */
export function primaryCategory(categories: string | null | undefined): string {
    return (categories ?? "").trim().split(/[\s,]+/)[0] ?? "";
}

/** "A, B, C, D" -> "A, B, C et al." */
export function shortAuthors(authors: string, max = 3): string {
    const list = authors
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean);
    if (list.length <= max) return list.join(", ");
    return `${list.slice(0, max).join(", ")} et al.`;
}

export function publishedYear(published: string | null): string {
    if (!published) return "";
    const year = new Date(published).getFullYear();
    return Number.isNaN(year) ? "" : String(year);
}

export function truncate(text: string, length: number): string {
    return text.length > length ? `${text.slice(0, length).trimEnd()}…` : text;
}
