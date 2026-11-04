import { Injectable } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';

/**
 * Citation and reference edges of a paper, limited to papers that are in the
 * database (edges to papers we have not fetched are kept, but not returned).
 *
 * Naming: paper_citation.cited_paper_entry_id is a paper that CITES the
 * belonging paper, paper_reference.referenced_paper_entry_id is a paper the
 * belonging paper cites.
 */
@Injectable()
export class EdgesService {
  constructor(private readonly db: DatabaseService) {}

  citationsOf(entryId: string) {
    return this.db
      .selectFrom('paper_citation as c')
      .innerJoin('paper as p', 'p.entry_id', 'c.cited_paper_entry_id')
      .select(['c.belonging_paper_entry_id', 'c.cited_paper_entry_id'])
      .where('c.belonging_paper_entry_id', '=', entryId)
      .execute();
  }

  referencesOf(entryId: string) {
    return this.db
      .selectFrom('paper_reference as r')
      .innerJoin('paper as p', 'p.entry_id', 'r.referenced_paper_entry_id')
      .select(['r.belonging_paper_entry_id', 'r.referenced_paper_entry_id'])
      .where('r.belonging_paper_entry_id', '=', entryId)
      .execute();
  }
}
