/**
 * Loads everything around one paper: the papers it cites, the papers citing
 * it and its related papers. The network view and the inspector both need
 * this, so the result is cached per paper and fetched only once.
 */
import { getCitingPapers, getPaper, getPapersByIds, getReferencedPapers } from "$lib/api";
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
    /** Related papers from Semantic Scholar, in their original order */
    related: Paper[];
    /** Citing / referenced papers outside arXiv, only counted */
    externalCitedBy: number;
    externalCites: number;
}

const cache = new Map<string, Promise<Neighbourhood>>();

async function load(entryId: string): Promise<Neighbourhood> {
    const [raw, citing, referenced] = await Promise.all([
        getPaper(entryId),
        getCitingPapers(entryId),
        getReferencedPapers(entryId),
    ]);
    const paper = toPaper(raw);
    if (!paper) throw new Error(`Paper ${entryId} has no data`);

    const relatedIds = toIdList(raw.related_arxiv_ids).slice(0, 30);
    const byId = new Map(toPapers(await getPapersByIds(relatedIds)).map((p) => [p.entry_id, p]));
    const related = relatedIds.map((id) => byId.get(id)).filter((p): p is Paper => !!p);

    return {
        paper,
        cites: toPapers(referenced.items),
        citedBy: toPapers(citing.items),
        citesTotal: referenced.total,
        citedByTotal: citing.total,
        related: related.filter((p) => p.entry_id !== entryId),
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
