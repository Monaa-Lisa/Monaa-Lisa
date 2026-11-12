/**
 * The one place that talks to the backend API.
 * Components call these functions instead of building URLs themselves.
 */
import { env } from "$env/dynamic/public";
import type { ApiPaper } from "$lib/types/paper";

export const API_BASE_URL = (env.PUBLIC_API_BASE_URL || "http://localhost:3000").replace(/\/+$/, "");

/** The backend never returns more papers than this in one request (MAX_TAKE). */
export const MAX_PAPERS_PER_REQUEST = 20000;
/** The batch endpoint accepts at most 5000 ids, we send smaller chunks. */
const BATCH_CHUNK_SIZE = 500;

export class ApiError extends Error {
    constructor(
        public status: number,
        message: string,
    ) {
        super(message);
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, init);
    if (!res.ok) throw new ApiError(res.status, `Request to ${path} failed (${res.status})`);
    return (await res.json()) as T;
}

export interface PaperQuery {
    search?: string;
    title?: string;
    author?: string;
    abstract?: string;
    categories?: string;
    dateFrom?: string;
    dateTo?: string;
    /** "relevance": best matches of `search` first (title and author matches, then the most cited) */
    sort?: "relevance" | "published" | "published_asc" | "citations";
    /** "map" leaves out the abstract and the citation lists, for the paper map */
    fields?: "full" | "map";
    /** "none" skips counting all matches (total is null), which is slow for common words */
    count?: "exact" | "none";
    skip?: number;
    take?: number;
}

export interface PaperPage {
    items: ApiPaper[];
    /** null when the request asked for count "none" */
    total: number | null;
    /** The search found nothing, the items are papers with a similar title */
    fuzzy?: boolean;
    skip: number;
    take: number;
}

/** GET /papers with search, filters and pagination. */
export function getPapers(query: PaperQuery): Promise<PaperPage> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== "") params.set(key, String(value));
    }
    return request<PaperPage>(`/papers?${params}`);
}

/** GET /papers/count: how many papers match the filters of a query. */
export async function countPapers(query: PaperQuery): Promise<number> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== "" && !["take", "skip", "sort", "fields", "count"].includes(key)) {
            params.set(key, String(value));
        }
    }
    return (await request<{ total: number }>(`/papers/count?${params}`)).total;
}

/** GET /papers/years: first and last year of publication in the dataset. */
export function getYearRange(): Promise<{ first: number | null; last: number | null }> {
    return request("/papers/years");
}

/** GET /papers/:id. Includes the citation and reference id lists. */
export function getPaper(entryId: string): Promise<ApiPaper> {
    return request<ApiPaper>(`/papers/${encodeURIComponent(entryId)}`);
}

/** POST /papers/batch, split into chunks. Unknown ids are left out of the result. */
export async function getPapersByIds(entryIds: string[]): Promise<ApiPaper[]> {
    const chunks: string[][] = [];
    for (let i = 0; i < entryIds.length; i += BATCH_CHUNK_SIZE) {
        chunks.push(entryIds.slice(i, i + BATCH_CHUNK_SIZE));
    }
    const results = await Promise.all(
        chunks.map((ids) =>
            request<ApiPaper[]>("/papers/batch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ entryIds: ids }),
            }),
        ),
    );
    return results.flat();
}

export interface CategoryCount {
    /** arXiv category, e.g. "cs.LG" */
    id: string;
    /** Papers of the dataset listed in the category, cross listed ones included */
    papers: number;
    /** Papers that have it as their primary category */
    primary: number;
}

/** GET /categories: how many papers of the dataset every category holds. */
export function getCategoryCounts(): Promise<CategoryCount[]> {
    return request<CategoryCount[]>("/categories");
}

export interface SimilarPapers {
    /** What "similar" means here: near in the embedding, near on the map, or nothing known */
    basis: "embedding" | "map" | null;
    /** Nearest first */
    items: ApiPaper[];
}

/** GET /papers/:id/similar: the papers nearest to this one. */
export function getSimilarPapers(entryId: string, take = 30): Promise<SimilarPapers> {
    return request<SimilarPapers>(`/papers/${encodeURIComponent(entryId)}/similar?take=${take}`);
}

export interface ConnectedPapers {
    by: "references" | "citations";
    /** Best score first; `shared` = common references, or papers citing both */
    items: (ApiPaper & { shared: number; score: number })[];
}

/**
 * GET /papers/:id/connected: papers that cite the same papers as this one
 * ("references", bibliographic coupling) or are cited together with it
 * ("citations", co-citation).
 */
export function getConnectedPapers(entryId: string, by: "references" | "citations"): Promise<ConnectedPapers> {
    return request<ConnectedPapers>(`/papers/${encodeURIComponent(entryId)}/connected?by=${by}`);
}

export interface PaperNeighbours {
    /** The most cited ones, at most 500 */
    items: ApiPaper[];
    /** How many there are in the dataset */
    total: number;
}

/** Papers in the dataset that cite this paper ("cited by" in the UI), most cited first. */
export function getCitingPapers(entryId: string): Promise<PaperNeighbours> {
    return request<PaperNeighbours>(`/paper-citations/paper/${encodeURIComponent(entryId)}`);
}

/** Papers in the dataset this paper references ("cites" in the UI), most cited first. */
export function getReferencedPapers(entryId: string): Promise<PaperNeighbours> {
    return request<PaperNeighbours>(`/paper-references/paper/${encodeURIComponent(entryId)}`);
}
