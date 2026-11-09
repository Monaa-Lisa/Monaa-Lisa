import { Injectable, NotFoundException } from '@nestjs/common';
import { sql } from 'kysely';
import type { Expression, SqlBool } from 'kysely';
import { DatabaseService } from '../database/database.service';
import { containsPattern } from '../database/sql';
import { DEFAULT_TAKE, MAX_TAKE, QueryPaperDto } from './dto/query-paper.dto';

/** Requests for more ids than this get no citation lists attached */
const ENRICH_LIMIT = 50;

/** Columns of a point on the paper map (fields=map) */
const MAP_COLUMNS = [
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
 * Read access to papers: search, pagination, single and batch lookups.
 * Nico, ported from Prisma to Kysely in Nov 2026.
 */
@Injectable()
export class PapersService {
  constructor(private readonly db: DatabaseService) {}

  /**
   * Search and list papers.
   * - search: matches title, authors or abstract (any of them)
   * - title / author / abstract: each must match its own column (all of them)
   * - categories: substring of the space separated category list
   * - dateFrom / dateTo: range on the published date
   */
  async findMany(q: QueryPaperDto) {
    const skip = q.skip ?? 0;
    // The DTO already limits take, this second guard keeps any caller from
    // loading the whole table in one request.
    const take = Math.min(q.take ?? DEFAULT_TAKE, MAX_TAKE);

    let query = this.db.selectFrom('paper').where((eb) => {
      const filters: Expression<SqlBool>[] = [];
      const search = q.search?.trim();
      if (search) {
        const pattern = containsPattern(search);
        filters.push(
          eb.or([
            eb('title', 'ilike', pattern),
            eb('authors', 'ilike', pattern),
            eb('abstract', 'ilike', pattern),
          ]),
        );
      }
      if (q.title?.trim())
        filters.push(eb('title', 'ilike', containsPattern(q.title.trim())));
      if (q.author?.trim())
        filters.push(eb('authors', 'ilike', containsPattern(q.author.trim())));
      if (q.abstract?.trim())
        filters.push(
          eb('abstract', 'ilike', containsPattern(q.abstract.trim())),
        );
      if (q.categories)
        filters.push(eb('categories', 'like', containsPattern(q.categories)));
      if (q.dateFrom) filters.push(eb('published', '>=', new Date(q.dateFrom)));
      if (q.dateTo) filters.push(eb('published', '<=', new Date(q.dateTo)));
      return eb.and(filters);
    });

    const countQuery = query.select((eb) =>
      eb.fn.countAll<string>().as('count'),
    );

    if (q.sort === 'citations') {
      // citations from arXiv papers plus the ones counted outside arXiv, id as
      // tiebreaker so pages never overlap (the expression has an index)
      query = query
        .orderBy(
          sql<number>`arxiv_citation_count + COALESCE(non_arxiv_citation_count, 0)`,
          'desc',
        )
        .orderBy('id', 'asc');
    } else {
      const direction = q.sort === 'published_asc' ? 'asc' : 'desc';
      query = query
        .orderBy('published', (ob) => ob[direction]().nullsLast())
        .orderBy('id', 'asc');
    }

    if (q.fields === 'map') {
      const [items, counted] = await Promise.all([
        query.select(MAP_COLUMNS).offset(skip).limit(take).execute(),
        countQuery.executeTakeFirstOrThrow(),
      ]);
      return { items, total: Number(counted.count), skip, take };
    }

    const [items, counted] = await Promise.all([
      query.selectAll().offset(skip).limit(take).execute(),
      countQuery.executeTakeFirstOrThrow(),
    ]);

    // the citation lists are only attached to short lists
    const enrich = take <= 40;
    return {
      items: enrich ? await this.withEdges(items) : items.map(withoutEdges),
      total: Number(counted.count),
      skip,
      take,
    };
  }

  /** One paper with its citation and reference ids, 404 if it is unknown. */
  async findByEntryId(entryId: string) {
    const paper = await this.db
      .selectFrom('paper')
      .selectAll()
      .where('entry_id', '=', entryId)
      .executeTakeFirst();
    if (!paper) throw new NotFoundException(`Paper ${entryId} not found`);
    const [withEdges] = await this.withEdges([paper]);
    return withEdges;
  }

  /** Several papers by id. Unknown ids are left out. */
  async findByEntryIds(entryIds: string[]) {
    if (!entryIds.length) return [];
    const papers = await this.db
      .selectFrom('paper')
      .selectAll()
      .where('entry_id', 'in', entryIds)
      .execute();
    return entryIds.length > ENRICH_LIMIT
      ? papers.map(withoutEdges)
      : this.withEdges(papers);
  }

  /**
   * Attaches the ids of citing papers (`citations`) and referenced papers
   * (`references`) from the two edge tables.
   */
  private async withEdges<T extends { entry_id: string }>(
    papers: T[],
  ): Promise<(T & { citations: string[]; references: string[] })[]> {
    if (!papers.length) return [];
    const ids = papers.map((p) => p.entry_id);

    const [citationRows, referenceRows] = await Promise.all([
      this.db
        .selectFrom('paper_citation')
        .select([
          'belonging_paper_entry_id as paper',
          'cited_paper_entry_id as other',
        ])
        .where('belonging_paper_entry_id', 'in', ids)
        .execute(),
      this.db
        .selectFrom('paper_reference')
        .select([
          'belonging_paper_entry_id as paper',
          'referenced_paper_entry_id as other',
        ])
        .where('belonging_paper_entry_id', 'in', ids)
        .execute(),
    ]);

    const citations = groupIds(citationRows);
    const references = groupIds(referenceRows);
    return papers.map((p) => ({
      ...p,
      citations: citations.get(p.entry_id) ?? [],
      references: references.get(p.entry_id) ?? [],
    }));
  }
}

function withoutEdges<T>(
  paper: T,
): T & { citations: string[]; references: string[] } {
  return { ...paper, citations: [], references: [] };
}

function groupIds(
  rows: { paper: string; other: string }[],
): Map<string, string[]> {
  const grouped = new Map<string, string[]>();
  for (const { paper, other } of rows) {
    const list = grouped.get(paper);
    if (list) list.push(other);
    else grouped.set(paper, [other]);
  }
  return grouped;
}
