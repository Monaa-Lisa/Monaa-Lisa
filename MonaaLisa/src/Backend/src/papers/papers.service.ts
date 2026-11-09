import { Injectable, NotFoundException } from '@nestjs/common';
import { sql } from 'kysely';
import type { Expression, Selectable, SqlBool } from 'kysely';
import type { Paper } from '../database/schema';
import { DatabaseService } from '../database/database.service';
import { containsPattern } from '../database/sql';
import { ALL_COLUMNS, LIST_COLUMNS, totalCitations } from './paper-columns';
import { arxivId, searchWords } from './search-text';
import { DEFAULT_TAKE, MAX_TAKE, QueryPaperDto } from './dto/query-paper.dto';

/** Requests for more ids than this get no citation lists attached */
const ENRICH_LIMIT = 50;
/** Papers returned by GET /papers/:entryId/similar */
export const DEFAULT_SIMILAR = 20;
const MAX_SIMILAR = 40;
/** Similar titles offered when a search finds nothing */
const FUZZY_LIMIT = 10;

/**
 * Read access to papers: search, pagination, single and batch lookups.
 * Nico, ported from Prisma to Kysely in Nov 2026.
 */
@Injectable()
export class PapersService {
  constructor(private readonly db: DatabaseService) {}

  /**
   * Search and list papers.
   * - search: an arXiv id, or words that all have to occur in the title, the
   *   authors or the abstract (in any order, each word in any of the three)
   * - title / author / abstract: every word must occur in that column
   * - categories: substring of the space separated category list
   * - dateFrom / dateTo: range on the published date
   * - sort=relevance: see `byRelevance`
   */
  async findMany(q: QueryPaperDto) {
    const skip = q.skip ?? 0;
    // The DTO already limits take, this second guard keeps any caller from
    // loading the whole table in one request.
    const take = Math.min(q.take ?? DEFAULT_TAKE, MAX_TAKE);

    // Counting every match of a common word takes seconds while the first
    // page is there at once, so a caller can leave the count out and ask
    // GET /papers/count for it.
    const total = q.count === 'none' ? Promise.resolve(null) : this.count(q);

    if (q.sort === 'relevance' && q.search?.trim() && skip === 0) {
      const [found, counted] = await Promise.all([
        this.byRelevance(q, take),
        total,
      ]);
      return {
        items: await this.shaped(found.items, q, take),
        total: found.fuzzy ? found.items.length : counted,
        skip,
        take,
        fuzzy: found.fuzzy,
      };
    }

    const [items, counted] = await Promise.all([
      this.sorted(this.filtered(q), q)
        .select(this.columns(q))
        .offset(skip)
        .limit(take)
        .execute(),
      total,
    ]);
    return {
      items: await this.shaped(items, q, take),
      total: counted,
      skip,
      take,
    };
  }

  /** First and last year of publication in the dataset (uses the index on published) */
  async years() {
    const { rows } = await sql<{ first: number | null; last: number | null }>`
      SELECT EXTRACT(YEAR FROM MIN(published))::int AS first,
             EXTRACT(YEAR FROM MAX(published))::int AS last
      FROM paper`.execute(this.db);
    return rows[0];
  }

  /** How many papers match the filters of `q` */
  async count(q: QueryPaperDto): Promise<number> {
    const counted = await this.filtered(q)
      .select((eb) => eb.fn.countAll<string>().as('count'))
      .executeTakeFirstOrThrow();
    return Number(counted.count);
  }

  /**
   * The best matches for a search text first:
   * 1. papers with all words in the title or the authors, most cited first
   * 2. then papers where some words are only in the abstract
   * 3. nothing found at all: titles that are similar to the text, which
   *    catches typing mistakes (`fuzzy` is true then)
   */
  private async byRelevance(q: QueryPaperDto, take: number) {
    const columns = this.columns(q);
    const mostCited = { ...q, sort: 'citations' as const };
    const items = await this.sorted(this.filtered(q, false), mostCited)
      .select(columns)
      .limit(take)
      .execute();

    if (items.length < take && !arxivId(q.search ?? '')) {
      let rest = this.filtered(q);
      if (items.length) {
        rest = rest.where(
          'entry_id',
          'not in',
          items.map((p) => p.entry_id),
        );
      }
      items.push(
        ...(await this.sorted(rest, mostCited)
          .select(columns)
          .limit(take - items.length)
          .execute()),
      );
    }
    if (items.length) return { items, fuzzy: false };

    const text = q.search!.trim();
    const similar = await this.filtered({ ...q, search: undefined })
      .where(sql<boolean>`${text} <% title`)
      .select(columns)
      .orderBy(sql`word_similarity(${text}, title)`, 'desc')
      .orderBy(totalCitations, 'desc')
      .limit(Math.min(take, FUZZY_LIMIT))
      .execute();
    return { items: similar, fuzzy: similar.length > 0 };
  }

  /** Slim columns for fields=map, everything otherwise */
  private columns(q: QueryPaperDto) {
    return q.fields === 'map' ? LIST_COLUMNS : ALL_COLUMNS;
  }

  /** Short full lists get their citation lists attached */
  private async shaped<T extends { entry_id: string }>(
    items: T[],
    q: QueryPaperDto,
    take: number,
  ) {
    if (q.fields === 'map') return items;
    return take <= 40 ? this.withEdges(items) : items.map(withoutEdges);
  }

  private sorted<Q extends ReturnType<PapersService['filtered']>>(
    query: Q,
    q: QueryPaperDto,
  ) {
    if (q.sort === 'citations' || q.sort === 'relevance') {
      // citations from arXiv papers plus the ones counted outside arXiv, id as
      // tiebreaker so pages never overlap (the expression has an index)
      return query.orderBy(totalCitations, 'desc').orderBy('id', 'asc');
    }
    const direction = q.sort === 'published_asc' ? 'asc' : 'desc';
    return query
      .orderBy('published', (ob) => ob[direction]().nullsLast())
      .orderBy('id', 'asc');
  }

  /**
   * The papers matching the filters of `q`. With `inAbstract` false the
   * search words have to be in the title or the authors.
   */
  private filtered(q: QueryPaperDto, inAbstract = true) {
    return this.db.selectFrom('paper').where((eb) => {
      const filters: Expression<SqlBool>[] = [];
      const search = q.search?.trim();
      const id = search ? arxivId(search) : null;
      if (id) {
        filters.push(eb('entry_id', '=', id));
      } else if (search) {
        for (const word of searchWords(search)) {
          // a short word has to stand alone ("AI" is not part of "training"),
          // a longer one may be part of a word ("network" finds "networks")
          const whole = /^[a-z0-9]{1,3}$/.test(word);
          const pattern = whole ? `\\m${word}\\M` : containsPattern(word);
          const op = whole ? '~*' : 'ilike';
          const anywhere = [
            eb('title', op, pattern),
            eb('authors', op, pattern),
          ];
          if (inAbstract) anywhere.push(eb('abstract', op, pattern));
          filters.push(eb.or(anywhere));
        }
      }
      const columns = {
        title: q.title,
        authors: q.author,
        abstract: q.abstract,
      };
      for (const [column, text] of Object.entries(columns)) {
        for (const word of searchWords(text ?? '')) {
          filters.push(
            eb(column as keyof typeof columns, 'ilike', containsPattern(word)),
          );
        }
      }
      if (q.categories)
        filters.push(eb('categories', 'like', containsPattern(q.categories)));
      if (q.dateFrom) filters.push(eb('published', '>=', new Date(q.dateFrom)));
      if (q.dateTo) filters.push(eb('published', '<=', new Date(q.dateTo)));
      return eb.and(filters);
    });
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

  /**
   * The papers most similar to one paper, nearest first, each with its
   * `distance`. `basis` says what the distance is:
   * - 'embedding': cosine distance of the 128-d embeddings
   * - 'map': distance on the 2-d map, for a paper whose embedding is not in
   *   the database (the map position is a projection of it, so this is a
   *   coarser version of the same thing)
   * - null: the paper has neither, `items` is empty
   */
  async similarTo(entryId: string, take = DEFAULT_SIMILAR) {
    const limit = Math.max(1, Math.min(take, MAX_SIMILAR));
    const columns = sql.join(LIST_COLUMNS.map((c) => sql.ref(`p.${c}`)));
    type Similar = Pick<Selectable<Paper>, (typeof LIST_COLUMNS)[number]> & {
      distance: number;
    };

    const embedded = await this.db
      .selectFrom('embedding')
      .select('id')
      .where('belonging_paper_entry_id', '=', entryId)
      .executeTakeFirst();
    if (embedded) {
      // the nearest embeddings first (uses the hnsw index), then their papers
      const own = sql`(SELECT content FROM embedding WHERE belonging_paper_entry_id = ${entryId})`;
      const { rows } = await sql<Similar>`
        SELECT ${columns}, n.distance
        FROM (
          SELECT e.belonging_paper_entry_id AS entry_id, e.content <=> ${own} AS distance
          FROM embedding e
          WHERE e.belonging_paper_entry_id <> ${entryId}
          ORDER BY e.content <=> ${own}
          LIMIT ${limit}
        ) n
        JOIN paper p ON p.entry_id = n.entry_id
        ORDER BY n.distance`.execute(this.db);
      return { basis: 'embedding' as const, items: rows };
    }

    // The position is read first and passed as a value: the index can only
    // serve a nearest neighbour search around a constant point.
    const own = await sql<{ x: number | null; y: number | null }>`
      SELECT (tsne->>'x')::float8 AS x, (tsne->>'y')::float8 AS y
      FROM paper WHERE entry_id = ${entryId}`.execute(this.db);
    const at = own.rows[0];
    if (at?.x == null || at.y == null) return { basis: null, items: [] };

    // same expression as the index paper_map_position_idx
    const position = sql`point((p.tsne->>'x')::float8, (p.tsne->>'y')::float8)`;
    const here = sql`point(${at.x}::float8, ${at.y}::float8)`;
    const { rows } = await sql<Similar>`
      SELECT ${columns}, ${position} <-> ${here} AS distance
      FROM paper p
      WHERE p.tsne IS NOT NULL AND p.entry_id <> ${entryId}
      ORDER BY ${position} <-> ${here}
      LIMIT ${limit}`.execute(this.db);
    return { basis: rows.length ? ('map' as const) : null, items: rows };
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
