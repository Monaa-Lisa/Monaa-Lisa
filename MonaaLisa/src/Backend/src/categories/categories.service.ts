import { Injectable } from '@nestjs/common';
import { sql } from 'kysely';
import { DatabaseService } from '../database/database.service';

export interface CategoryCount {
  /** arXiv category, e.g. "cs.LG" */
  id: string;
  /** Papers listed in the category, cross listed ones included */
  papers: number;
  /** Papers that have it as their primary (first) category */
  primary: number;
}

/** Counting reads the whole paper table, the answer is kept this long */
const KEEP_MS = 60 * 60 * 1000;

/** How many papers of the dataset every arXiv category holds. */
@Injectable()
export class CategoriesService {
  constructor(private readonly db: DatabaseService) {}

  private kept: { at: number; counts: Promise<CategoryCount[]> } | null = null;

  counts(): Promise<CategoryCount[]> {
    if (!this.kept || Date.now() - this.kept.at > KEEP_MS) {
      const counts = this.count();
      this.kept = { at: Date.now(), counts };
      // a failed count is not kept, the next request tries again
      counts.catch(() => (this.kept = null));
    }
    return this.kept.counts;
  }

  private async count(): Promise<CategoryCount[]> {
    const { rows } = await sql<CategoryCount>`
      SELECT c.id,
             COUNT(*)::int AS papers,
             COUNT(*) FILTER (WHERE c.position = 1)::int AS "primary"
      FROM paper p,
           unnest(string_to_array(trim(p.categories), ' ')) WITH ORDINALITY AS c(id, position)
      WHERE p.categories IS NOT NULL AND c.id <> ''
      GROUP BY c.id
      ORDER BY papers DESC`.execute(this.db);
    return rows;
  }
}
