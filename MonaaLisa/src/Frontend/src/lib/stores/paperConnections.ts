import { writable, derived } from 'svelte/store';
import { fetchPaperCitations, fetchPaperReferences, fetchRelationsForPaper } from '$lib/api';
import type { Paper } from '$lib/types/paper';

export interface PaperConnection {
  entry_id: string;
  paper?: Paper; // The actual paper object if found in dataset
  type: 'citation' | 'reference' | 'relation';
  // Raw data from API
  raw?: any;
}

export interface PaperConnectionsState {
  selectedPaperId: string | null;
  citations: PaperConnection[];
  references: PaperConnection[];
  relations: PaperConnection[];
  loading: boolean;
  error: string | null;
}

const initialState: PaperConnectionsState = {
  selectedPaperId: null,
  citations: [],
  references: [],
  relations: [],
  loading: false,
  error: null
};

function createPaperConnectionsStore() {
  const { subscribe, set, update } = writable<PaperConnectionsState>(initialState);

  let papersLookup: Map<string, Paper> = new Map();

  return {
    subscribe,

    /**
     * Set the papers lookup map for resolving paper details
     */
    setPapersLookup(papers: Paper[]) {
      papersLookup = new Map();
      papers.forEach(p => {
        if (p.entry_id) {
          papersLookup.set(p.entry_id, p);
        }
      });
    },

    /**
     * Fetch connections for a paper and update the store
     */
    async fetchConnections(paperId: string) {
      update(state => ({
        ...state,
        selectedPaperId: paperId,
        loading: true,
        error: null
      }));

      try {
        const [citationsRaw, referencesRaw, relationsRaw] = await Promise.all([
          fetchPaperCitations(paperId),
          fetchPaperReferences(paperId),
          fetchRelationsForPaper(paperId)
        ]);

        // Process citations - extract entry_ids and resolve papers
        const citations: PaperConnection[] = citationsRaw.map((item: any) => {
          const candidateIds = [
            item.cited_paper_entry_id,
            item.source_entry_id,
            item.target_entry_id,
            item.entry_id,
            item.id
          ].filter(Boolean);

          // Find an ID that is not the selected paper
          const entryId = candidateIds.find(id => String(id) !== String(paperId)) || candidateIds[0];
          const entryIdStr = String(entryId);

          return {
            entry_id: entryIdStr,
            paper: papersLookup.get(entryIdStr),
            type: 'citation' as const,
            raw: item
          };
        });

        // Process references
        const references: PaperConnection[] = referencesRaw.map((item: any) => {
          const candidateIds = [
            item.referenced_paper_entry_id,
            item.source_entry_id,
            item.target_entry_id,
            item.entry_id,
            item.id
          ].filter(Boolean);

          const entryId = candidateIds.find(id => String(id) !== String(paperId)) || candidateIds[0];
          const entryIdStr = String(entryId);

          return {
            entry_id: entryIdStr,
            paper: papersLookup.get(entryIdStr),
            type: 'reference' as const,
            raw: item
          };
        });

        // Process relations
        const relations: PaperConnection[] = relationsRaw.map((item: any) => {
          // Relation has source_id and target_id - find the one that is NOT the selected paper
          const sourceId = item.source_id;
          const targetId = item.target_id;

          // Pick the "other" paper ID (not the currently selected one)
          let entryIdStr: string;
          if (String(sourceId) === String(paperId)) {
            entryIdStr = String(targetId);
          } else {
            entryIdStr = String(sourceId);
          }

          return {
            entry_id: entryIdStr,
            paper: papersLookup.get(entryIdStr),
            type: 'relation' as const,
            raw: item
          };
        });

        update(state => ({
          ...state,
          citations,
          references,
          relations,
          loading: false
        }));

        return { citations, references, relations };
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to fetch connections';
        update(state => ({
          ...state,
          loading: false,
          error: errorMsg
        }));
        throw err;
      }
    },

    /**
     * Clear the current selection and connections
     */
    clear() {
      set(initialState);
    },

    /**
     * Get a paper by entry_id from the lookup
     */
    getPaper(entryId: string): Paper | undefined {
      return papersLookup.get(entryId);
    }
  };
}

export const paperConnections = createPaperConnectionsStore();

// Derived store for easy access to citations with resolved papers
export const citationsWithPapers = derived(
  paperConnections,
  $state => $state.citations.filter(c => c.paper)
);

// Derived store for references with resolved papers
export const referencesWithPapers = derived(
  paperConnections,
  $state => $state.references.filter(r => r.paper)
);

// Derived store for relations with resolved papers
export const relationsWithPapers = derived(
  paperConnections,
  $state => $state.relations.filter(r => r.paper)
);

