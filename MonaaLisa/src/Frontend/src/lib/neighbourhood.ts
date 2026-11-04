/**
 * Loads everything around one paper: the papers it cites, the papers citing
 * it and its related papers. The network view and the inspector both need
 * this, so the result is cached per paper and fetched only once.
 */
import { getCitationEdges, getPaper, getPapersByIds, getReferenceEdges } from "$lib/api";
import { toIdList, toPaper, toPapers } from "$lib/paper";
import type { Paper } from "$lib/types/paper";

export interface Neighbourhood {
    /** The paper itself, fully loaded */
    paper: Paper;
    /** Papers this paper references (that are in our database) */
    cites: Paper[];
    /** Papers that cite this paper (that are in our database) */
    citedBy: Paper[];
    /** Related papers from Semantic Scholar, in their original order */
    related: Paper[];
    /** Citing / referenced papers outside arXiv, only counted */
    externalCitedBy: number;
    externalCites: number;
}

const cache = new Map<string, Promise<Neighbourhood>>();

async function load(entryId: string): Promise<Neighbourhood> {
    const [raw, citationEdges, referenceEdges] = await Promise.all([
        getPaper(entryId),
        getCitationEdges(entryId),
        getReferenceEdges(entryId),
    ]);
    const paper = toPaper(raw);
    if (!paper) throw new Error(`Paper ${entryId} has no data`);

    // paper_citation.cited_paper_entry_id holds the papers citing this one
    const citedByIds = [...new Set(citationEdges.map((e) => e.cited_paper_entry_id))];
    const citesIds = [...new Set(referenceEdges.map((e) => e.referenced_paper_entry_id))];
    const relatedIds = toIdList(raw.related_arxiv_ids).slice(0, 30);

    const papers = toPapers(await getPapersByIds([...new Set([...citedByIds, ...citesIds, ...relatedIds])]));
    const byId = new Map(papers.map((p) => [p.entry_id, p]));
    const pick = (ids: string[]) => ids.map((id) => byId.get(id)).filter((p): p is Paper => !!p);

    return {
        paper,
        cites: pick(citesIds),
        citedBy: pick(citedByIds),
        related: pick(relatedIds).filter((p) => p.entry_id !== entryId),
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
