/**
 * Raw paper object as returned by the NestJS backend API.
 */
export interface ApiPaper {
    id?: number;
    entry_id: string;
    title: string;
    authors?: string | string[];
    abstract?: string | null;
    categories?: string | null;
    published?: string | null;
    updated?: string | null;
    doi?: string | null;
    journal_ref?: string | null;
    license?: string | null;
    url?: string | null;
    s2_id?: string | null;
    non_arxiv_citation_count?: number | null;
    non_arxiv_reference_count?: number | null;
    arxiv_citation_count?: number | null;
    tsne?: unknown;
    related_arxiv_ids?: unknown;
    citations?: unknown;
    references?: unknown;
}

/**
 * Normalised paper used by the components.
 */
export interface Paper {
    id: number;
    entry_id: string;
    title: string;
    /** Author names as stored by arXiv, separated by "," or " and " */
    authors: string;
    abstract: string;
    published: string | null;
    updated: string | null;
    categories: string | null;
    doi: string | null;
    journal_ref: string | null;
    s2_id: string | null;
    /** arXiv ids of papers citing this one (only filled by some endpoints) */
    citations: string[];
    /** arXiv ids of papers this one cites (only filled by some endpoints) */
    references: string[];
    /** Citing / referenced papers that are not on arXiv (Semantic Scholar counts) */
    non_arxiv_citation_count: number;
    non_arxiv_reference_count: number;
    /** Papers on arXiv citing this one, as counted by the pipeline */
    arxiv_citation_count: number;
    /** Map position (UMAP of the SPECTER2 embedding), 0/0 when unknown */
    x: number;
    y: number;
}

/**
 * One node of the arXiv category hierarchy (a subject or a subcategory).
 */
export interface CategoryNode {
    id: string;
    name: string;
    /** Papers in this category: in the dataset, or arXiv wide until the dataset is counted */
    count: number;
}
