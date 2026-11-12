import { sql } from 'kysely';

/**
 * Columns of a paper in lists and on the maps: everything but the abstract
 * and the other long fields.
 */
export const LIST_COLUMNS = [
  'id',
  'entry_id',
  'title',
  'authors',
  'categories',
  'published',
  'tsne',
  'arxiv_citation_count',
  'non_arxiv_citation_count',
] as const;

/**
 * All known citations of a paper: from arXiv papers plus the ones counted
 * outside arXiv. Has an index (paper_total_citation_count_id_idx), keep the
 * expression exactly as it is there.
 */
export const totalCitations = sql<number>`arxiv_citation_count + COALESCE(non_arxiv_citation_count, 0)`;

/** Every column of a paper */
export const ALL_COLUMNS = [
  ...LIST_COLUMNS,
  'abstract',
  'updated',
  'doi',
  'journal_ref',
  'license',
  'url',
  's2_id',
  'non_arxiv_reference_count',
  'related_arxiv_ids',
] as const;
