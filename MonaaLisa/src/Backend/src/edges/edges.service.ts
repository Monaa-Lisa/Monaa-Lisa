import { Injectable } from '@nestjs/common';
import type { SelectQueryBuilder } from 'kysely';
import { DatabaseService } from '../database/database.service';
import type { DB } from '../database/schema';
import { LIST_COLUMNS, totalCitations } from '../papers/paper-columns';

/** Most papers one request returns, the most cited ones come first */
export const MAX_NEIGHBOURS = 2000;
export const DEFAULT_NEIGHBOURS = 500;

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
