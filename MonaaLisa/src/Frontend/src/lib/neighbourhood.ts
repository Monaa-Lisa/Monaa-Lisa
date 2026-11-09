/**
 * Loads everything around one paper: the papers it cites, the papers citing
 * it and the papers similar to it. The network view and the inspector both need
 * this, so the result is cached per paper and fetched only once.
 */
import { getCitingPapers, getConnectedPapers, getPaper, getPapersByIds, getReferencedPapers, getSimilarPapers } from "$lib/api";
import { toIdList, toPaper, toPapers } from "$lib/paper";
import type { Paper } from "$lib/types/paper";

export interface Neighbourhood {
    /** The paper itself, fully loaded */
    paper: Paper;
    /** Papers this paper references that are in the dataset, the most cited ones (at most 500) */
    cites: Paper[];
    /** Papers in the dataset that cite this paper, the most cited ones (at most 500) */
    citedBy: Paper[];
    /** How many of each the dataset holds */
    citesTotal: number;
    citedByTotal: number;
    /** Similar papers, the most similar first */
    related: Paper[];
    /**
     * Where they come from: the nearest papers in the embedding, the nearest
     * on the map (the embedding of this paper is not in the database), or
     * the recommendations of Semantic Scholar when the paper has no position
     */
    relatedBasis: "embedding" | "map" | "semantic-scholar";
    /** Citing / referenced papers outside arXiv, only counted */
    externalCitedBy: number;
    externalCites: number;
}

const cache = new Map<string, Promise<Neighbourhood>>();

async function load(entryId: string): Promise<Neighbourhood> {
    const [raw, citing, referenced, similar] = await Promise.all([
        getPaper(entryId),
        getCitingPapers(entryId),
        getReferencedPapers(entryId),
        getSimilarPapers(entryId),
    ]);
    const paper = toPaper(raw);
    if (!paper) throw new Error(`Paper ${entryId} has no data`);

    let related = toPapers(similar.items);
    if (!similar.basis) {
        const relatedIds = toIdList(raw.related_arxiv_ids).slice(0, 30);
        const byId = new Map(toPapers(await getPapersByIds(relatedIds)).map((p) => [p.entry_id, p]));
        related = relatedIds.map((id) => byId.get(id)).filter((p): p is Paper => !!p);
    }

    return {
        paper,
        cites: toPapers(referenced.items),
        citedBy: toPapers(citing.items),
        citesTotal: referenced.total,
        citedByTotal: citing.total,
        related: related.filter((p) => p.entry_id !== entryId),
        relatedBasis: similar.basis ?? "semantic-scholar",
        externalCitedBy: paper.non_arxiv_citation_count,
        externalCites: paper.non_arxiv_reference_count,
    };
}

export function loadNeighbourhood(entryId: string): Promise<Neighbourhood> {
    let pending = cache.get(entryId);
    if (!pending) {
        pending = load(entryId);
        // do not keep failed requests, so a retry can succeed
        pending.catch(() => cache.delete(entryId));
        cache.set(entryId, pending);
    }
    return pending;
}

/**
 * The three ways the "Similar" tab can find papers:
 *   content     nearest in the embedding (or on the map), see Neighbourhood.related
 *   references  papers citing the same papers (bibliographic coupling)
 *   citations   papers cited together with this one (co-citation)
 */
export type SimilarBy = "content" | "references" | "citations";

export interface Connected {
    /** Strongest connection first */
    papers: Paper[];
    /** Common references, or papers citing both, per paper */
    shared: Map<string, number>;
}

const connectedCache = new Map<string, Promise<Connected>>();

export function loadConnected(entryId: string, by: "references" | "citations"): Promise<Connected> {
    const key = `${by}:${entryId}`;
    let pending = connectedCache.get(key);
    if (!pending) {
        pending = getConnectedPapers(entryId, by).then(({ items }) => ({
            papers: toPapers(items),
            shared: new Map(items.map((p) => [p.entry_id, p.shared])),
        }));
        pending.catch(() => connectedCache.delete(key));
        connectedCache.set(key, pending);
    }
    return pending;
}
