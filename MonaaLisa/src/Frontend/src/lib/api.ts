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
    sort?: "published" | "published_asc" | "citations";
    /** "map" leaves out the abstract and the citation lists, for the paper map */
    fields?: "full" | "map";
    skip?: number;
    take?: number;
}

export interface PaperPage {
    items: ApiPaper[];
    total: number;
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

export interface CitationEdge {
    belonging_paper_entry_id: string;
    cited_paper_entry_id: string;
}

export interface ReferenceEdge {
    belonging_paper_entry_id: string;
    referenced_paper_entry_id: string;
}

/**
 * Citation edges of a paper. Careful with the naming: cited_paper_entry_id
 * is a paper that CITES this paper (it is "cited by" in the UI).
 */
export function getCitationEdges(entryId: string): Promise<CitationEdge[]> {
    return request<CitationEdge[]>(`/paper-citations/paper/${encodeURIComponent(entryId)}`);
}

/** Papers this paper references ("cites" in the UI). */
export function getReferenceEdges(entryId: string): Promise<ReferenceEdge[]> {
    return request<ReferenceEdge[]>(`/paper-references/paper/${encodeURIComponent(entryId)}`);
}
