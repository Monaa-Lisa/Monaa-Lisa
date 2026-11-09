import { Injectable } from '@nestjs/common';
import { sql } from 'kysely';
import type { Selectable, SelectQueryBuilder } from 'kysely';
import { DatabaseService } from '../database/database.service';
import type { DB, Paper } from '../database/schema';
import { LIST_COLUMNS, totalCitations } from '../papers/paper-columns';

/** Most papers one request returns, the most cited ones come first */
export const MAX_NEIGHBOURS = 2000;
export const DEFAULT_NEIGHBOURS = 500;

/** Papers returned by GET /papers/:entryId/connected */
export const DEFAULT_CONNECTED = 30;
const MAX_CONNECTED = 100;
/** Links of the paper itself that are followed, the newest for a paper with more */
const MAX_LINKS_READ = 3000;
/** Papers with the most shared links that get a score */
const CANDIDATES = 200;

/**
 * The papers citing a paper and the papers it cites, limited to papers that
 * are in the database.
 *
 * Both edge tables are read for both directions. Semantic Scholar caps the
 * list of citing papers for popular ones (paper_citation then only holds the
 * newest few thousand), but every citing paper in the database lists the
 * paper among its references, so the reference table fills the gap.
 *
 * Naming: paper_citation.cited_paper_entry_id is a paper that CITES the
 * belonging paper, paper_reference.referenced_paper_entry_id is a paper the
 * belonging paper cites.
 */
@Injectable()
export class EdgesService {
  constructor(private readonly db: DatabaseService) {}

  /** Papers that cite `entryId` */
  citationsOf(entryId: string, take = DEFAULT_NEIGHBOURS) {
    const ids = this.db
      .selectFrom('paper_citation')
      .select('cited_paper_entry_id as entry_id')
      .where('belonging_paper_entry_id', '=', entryId)
      .union(
        this.db
          .selectFrom('paper_reference')
          .select('belonging_paper_entry_id as entry_id')
          .where('referenced_paper_entry_id', '=', entryId),
      );
    return this.papers(entryId, ids, take);
  }

  /** Papers that `entryId` cites */
  referencesOf(entryId: string, take = DEFAULT_NEIGHBOURS) {
    const ids = this.db
      .selectFrom('paper_reference')
      .select('referenced_paper_entry_id as entry_id')
      .where('belonging_paper_entry_id', '=', entryId)
      .union(
        this.db
          .selectFrom('paper_citation')
          .select('belonging_paper_entry_id as entry_id')
          .where('cited_paper_entry_id', '=', entryId),
      );
    return this.papers(entryId, ids, take);
  }

  /**
   * Papers connected to `entryId` through the citation graph, the two
   * classic measures of bibliometrics:
   * - 'references': bibliographic coupling (Kessler 1963), papers that cite
   *   the same papers. `shared` is the number of common references.
   * - 'citations': co-citation (Small 1973), papers that are cited together
   *   with it. `shared` is the number of papers citing both. For a paper
   *   with very many citations only its newest citing papers are read.
   * `score` is `shared` divided by the geometric mean of the two list
   * lengths (Salton's cosine), so a survey with hundreds of references or a
   * paper everybody cites does not win by size alone. Ordered by score.
   */
  async connectedTo(
    entryId: string,
    by: 'references' | 'citations',
    take = DEFAULT_CONNECTED,
  ) {
    const limit = Math.max(1, Math.min(take, MAX_CONNECTED));
    // own: the papers on the far side of this paper's links
    // other: every paper with a link to one of them
    const [near, far] =
      by === 'references'
        ? [
            sql.ref('belonging_paper_entry_id'),
            sql.ref('referenced_paper_entry_id'),
          ]
        : [
            sql.ref('referenced_paper_entry_id'),
            sql.ref('belonging_paper_entry_id'),
          ];
    const columns = sql.join(LIST_COLUMNS.map((c) => sql.ref(`p.${c}`)));
    type Connected = Pick<Selectable<Paper>, (typeof LIST_COLUMNS)[number]> & {
      shared: number;
      score: number;
    };
    const { rows } = await sql<Connected>`
      WITH own AS (
        SELECT ${far} AS id FROM paper_reference
        WHERE ${near} = ${entryId}
        ORDER BY ${far} DESC
        LIMIT ${MAX_LINKS_READ}
      ),
      candidate AS (
        SELECT r.${near} AS id, COUNT(*) AS shared
        FROM own JOIN paper_reference r ON r.${far} = own.id
        WHERE r.${near} <> ${entryId}
        GROUP BY r.${near}
        HAVING COUNT(*) >= 2
        ORDER BY shared DESC
        LIMIT ${CANDIDATES}
      ),
      sized AS (
        SELECT c.id, c.shared,
               (SELECT COUNT(*) FROM paper_reference x WHERE x.${near} = c.id) AS size
        FROM candidate c
      )
      SELECT ${columns}, s.shared::int AS shared,
             (s.shared / sqrt(s.size * (SELECT COUNT(*) FROM own)))::float8 AS score
      FROM sized s JOIN paper p ON p.entry_id = s.id
      ORDER BY score DESC, p.id
      LIMIT ${limit}`.execute(this.db);
    return { by, items: rows };
  }

  private async papers<T extends keyof DB>(
    entryId: string,
    ids: SelectQueryBuilder<DB, T, { entry_id: string }>,
    take: number,
  ) {
    const limit = Math.max(1, Math.min(take, MAX_NEIGHBOURS));
    // The neighbours are collected first and sorted afterwards. In one plain
    // query Postgres walks the whole citation order index for a small limit,
    // which takes minutes for a paper with many citations.
    const rows = await this.db
      .with(
        (cte) => cte('neighbour').materialized(),
        (db) =>
          db
            .selectFrom('paper')
            .select(LIST_COLUMNS)
            .select(totalCitations.as('citations'))
            .where('entry_id', 'in', ids)
            .where('entry_id', '!=', entryId),
      )
      .selectFrom('neighbour')
      .selectAll()
      .select((eb) => eb.fn.countAll<string>().over().as('total'))
      .orderBy('citations', 'desc')
      .orderBy('id', 'asc')
      .limit(limit)
      .execute();
    return {
      total: rows.length ? Number(rows[0].total) : 0,
      items: rows.map((row) => {
        const paper: Partial<typeof row> = { ...row };
        delete paper.total;
        delete paper.citations;
        return paper;
      }),
    };
  }
}
