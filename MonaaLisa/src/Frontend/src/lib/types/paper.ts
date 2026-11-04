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
    tsne?: unknown;
    related_arxiv_ids?: unknown;
    citations?: unknown;
    references?: unknown;
    cluster?: string | null;
}

/**
 * Normalised paper used internally by the frontend components.
 */
export interface Paper {
    id: number;
    entry_id: string;
    title: string;
    authors: string;
    abstract: string;
    published: string | null;
    categories: string | null;
    url: string | null;
    citations: string[];
    references: string[];
    non_arxiv_citation_count: number;
    non_arxiv_reference_count: number;
    tsne1: number;
    tsne2: number;
    cluster: string;
}

/**
 * Cluster node for hierarchical category navigation.
 */
export interface ClusterNode {
    id: string;
    name: string;
    count: number;
}
