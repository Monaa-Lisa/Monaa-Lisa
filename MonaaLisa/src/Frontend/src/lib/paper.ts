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
        title: raw.title.replace(/\s+/g, " ").trim(),
        authors: authorsToString(raw.authors),
        abstract: (raw.abstract ?? "").replace(/\s+/g, " ").trim(),
        published: raw.published ?? null,
        updated: raw.updated ?? null,
        categories: raw.categories ?? null,
        doi: raw.doi ?? null,
        journal_ref: raw.journal_ref ?? null,
        s2_id: raw.s2_id ?? null,
        citations: toIdList(raw.citations),
        references: toIdList(raw.references),
        non_arxiv_citation_count: raw.non_arxiv_citation_count ?? 0,
        non_arxiv_reference_count: raw.non_arxiv_reference_count ?? 0,
        arxiv_citation_count: raw.arxiv_citation_count ?? 0,
        x,
        y,
    };
}

export function toPapers(items: ApiPaper[]): Paper[] {
    return items.map(toPaper).filter((p): p is Paper => p !== null);
}

/** First (primary) category of a paper, e.g. "cs.LG". */
export function primaryCategory(categories: string | null | undefined): string {
    return (categories ?? "").trim().split(/[\s,]+/)[0] ?? "";
}

/** All categories of a paper as a list. */
export function categoryList(categories: string | null | undefined): string[] {
    return (categories ?? "")
        .trim()
        .split(/[\s,]+/)
        .filter(Boolean);
}

/**
 * Author names as a list. arXiv separates authors with "," or " and " and
 * sometimes appends affiliations in parentheses, which are dropped here.
 */
export function authorList(authors: string): string[] {
    return authors
        .replace(/\([^)]*\)/g, " ")
        .split(/,|\band\b/)
        .map((a) => a.replace(/\s+/g, " ").trim())
        .filter(Boolean);
}

/** "A, B, C, D" -> "A, B, C et al." */
export function shortAuthors(authors: string, max = 3): string {
    const list = authorList(authors);
    if (list.length <= max) return list.join(", ");
    return `${list.slice(0, max).join(", ")} et al.`;
}

export function publishedYear(published: string | null): string {
    if (!published) return "";
    const year = new Date(published).getFullYear();
    return Number.isNaN(year) ? "" : String(year);
}

/** "2009-12-29T..." -> "29 Dec 2009" */
export function formatDate(iso: string | null): string {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function truncate(text: string, length: number): string {
    return text.length > length ? `${text.slice(0, length).trimEnd()}…` : text;
}

/** Citations known for a paper: on arXiv plus the Semantic Scholar count outside arXiv. */
export function citationCount(p: Paper): number {
    return Math.max(p.arxiv_citation_count, p.citations.length) + p.non_arxiv_citation_count;
}

/** Links to the paper elsewhere. */
export function paperLinks(p: Paper) {
    const id = encodeURIComponent(p.entry_id);
    return {
        arxiv: `https://arxiv.org/abs/${id}`,
        pdf: `https://arxiv.org/pdf/${id}`,
        doi: p.doi ? `https://doi.org/${p.doi}` : null,
        semanticScholar: p.s2_id ? `https://www.semanticscholar.org/paper/${encodeURIComponent(p.s2_id)}` : null,
    };
}

/**
 * BibTeX entry in the form arXiv itself exports: @misc with an eprint field.
 * The key is first author surname + year + first title word, e.g. goldenberg2009survey.
 */
export function toBibtex(p: Paper): string {
    const authors = authorList(p.authors);
    const year = publishedYear(p.published);
    const surname = (authors[0] ?? "arxiv").split(" ").pop() ?? "arxiv";
    const word = p.title.split(/\s+/).find((w) => w.length > 3) ?? "paper";
    const key = `${surname}${year}${word}`.toLowerCase().replace(/[^a-z0-9]/g, "");
    const escape = (s: string) => s.replace(/[{}]/g, "").replace(/([&%$#_])/g, "\\$1");
    const fields: [string, string][] = [
        ["title", escape(p.title)],
        ["author", authors.map(escape).join(" and ")],
        ["year", year],
        ["eprint", p.entry_id],
        ["archivePrefix", "arXiv"],
        ["primaryClass", primaryCategory(p.categories)],
    ];
    if (p.doi) fields.push(["doi", p.doi]);
    if (p.journal_ref) fields.push(["journal", escape(p.journal_ref)]);
    fields.push(["url", paperLinks(p).arxiv]);
    const body = fields
        .filter(([, v]) => v)
        .map(([k, v]) => `  ${k} = {${v}}`)
        .join(",\n");
    return `@misc{${key},\n${body}\n}`;
}
