import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { Prisma } from '@prisma/client';
import {
  DEFAULT_TAKE,
  MAX_TAKE,
  PaperSort,
  QueryPaperDto,
} from './dto/query-paper.dto';

/**
 * PapersService Nico
 * -------------------------------
 * Read access to papers: search, pagination, single and batch lookups.
 */
@Injectable()
export class PapersService {
  constructor(private prisma: PrismaService) {}

  /**
   * Sucht Papers mit Volltext-Like über `title`, `authors`, `summary`,
   * plus optionaler Kategorie & Datumsbereich.
   * Pagination via `skip`/`take`, dazu Gesamtanzahl für UI.
   */
  // `MonaaLisa/src/Backend/src/papers/papers.service.ts`

  async findMany(q: QueryPaperDto) {
    const skip = toNumber(q.skip, 0);
    // The DTO already limits take, this is a second guard so no caller can
    // ever load the whole table in one request.
    const take = Math.min(toNumber(q.take, DEFAULT_TAKE), MAX_TAKE);

    // ── sort=citations → raw SQL path (order by citation count DESC) ──
    if (
      q.sort === 'citations' &&
      q.categories &&
      !q.search &&
      !q.title &&
      !q.author &&
      !q.abstract &&
      !q.dateFrom &&
      !q.dateTo
    ) {
      return this.findManyByCitationCount(q.categories, skip, take);
    }

    const where: Prisma.PaperWhereInput = {};

    if (q.search && q.search.trim() !== '') {
      const term = q.search.trim();
      where.OR = [
        { title: { contains: term, mode: 'insensitive' } },
        { authors: { contains: term, mode: 'insensitive' } },
        { abstract: { contains: term, mode: 'insensitive' } },
      ];
    }

    // Each advanced field must match on its own column
    const fieldFilters: Prisma.PaperWhereInput[] = [];
    if (q.title?.trim()) {
      fieldFilters.push({
        title: { contains: q.title.trim(), mode: 'insensitive' },
      });
    }
    if (q.author?.trim()) {
      fieldFilters.push({
        authors: { contains: q.author.trim(), mode: 'insensitive' },
      });
    }
    if (q.abstract?.trim()) {
      fieldFilters.push({
        abstract: { contains: q.abstract.trim(), mode: 'insensitive' },
      });
    }
    if (fieldFilters.length) where.AND = fieldFilters;

    if (q.categories) where.categories = { contains: q.categories };

    if (q.dateFrom || q.dateTo) {
      const publishedFilter: Prisma.DateTimeNullableFilter = {};
      if (q.dateFrom) publishedFilter.gte = new Date(q.dateFrom);
      if (q.dateTo) publishedFilter.lte = new Date(q.dateTo);
      where.published = publishedFilter;
    }

    const [items, total] = await Promise.all([
      this.prisma.paper.findMany({
        where,
        orderBy: orderByFor(q.sort),
        skip,
        take,
      }),
      this.prisma.paper.count({ where }),
    ]);

    const shouldEnrich = take <= 40;

    const enrichedItems = shouldEnrich
      ? await this.enrichWithCitations(items)
      : items.map((p) => ({ ...p, citations: [], references: [] }));

    return { items: enrichedItems, total, skip, take };
  }

  /**
   * Papers of one category, most cited (by arXiv papers) first.
   * Uses the stored arxiv_citation_count and its index, with id as tiebreaker
   * so that pages do not overlap when many papers have the same count.
   */
  private async findManyByCitationCount(
    category: string,
    skip: number,
    take: number,
  ) {
    const where: Prisma.PaperWhereInput = {
      categories: { contains: category },
    };
    const [papers, total] = await Promise.all([
      this.prisma.paper.findMany({
        where,
        orderBy: [{ arxiv_citation_count: 'desc' }, { id: 'asc' }],
        skip,
        take,
      }),
      this.prisma.paper.count({ where }),
    ]);

    const items = await this.enrichWithCitations(papers);
    return { items, total, skip, take };
  }

  /**
   * Returns one paper by `entry_id` with its citation and reference ids.
   * Responds with 404 if the paper is not in the database.
   */
  async findByEntryId(entry_id: string) {
    const paper = await this.prisma.paper.findUnique({ where: { entry_id } });
    if (!paper) throw new NotFoundException(`Paper ${entry_id} not found`);
    const [citations, references] = await Promise.all([
      this.prisma.paperCitation.findMany({
        where: { belonging_paper_entry_id: entry_id },
        select: { cited_paper_entry_id: true },
      }),
      this.prisma.paperReference.findMany({
        where: { belonging_paper_entry_id: entry_id },
        select: { referenced_paper_entry_id: true },
      }),
    ]);
    return {
      ...paper,
      citations: citations.map((c) => c.cited_paper_entry_id),
      references: references.map((r) => r.referenced_paper_entry_id),
    };
  }

  /**
   * Batch-Fetch: holt mehrere Papers anhand einer Liste von `entry_id`s.
   * Maximal 5000 Ergebnisse.
   */
  async findByEntryIds(entryIds: string[], take = 5000) {
    const papers = await this.prisma.paper.findMany({
      where: { entry_id: { in: entryIds } },
      take,
    });

    // Falls jemand 5000 IDs anfragt, NIEMALS enrichWithCitations machen
    if (entryIds.length > 50) {
      return papers.map((p) => ({ ...p, citations: [], references: [] }));
    }

    return this.enrichWithCitations(papers);
  }

  /**
   * Holt aus der paper_citation- und paper_reference-Tabelle die IDs für
   * jedes übergebene Paper und hängt sie als `citations` / `references` an.
   */
  private async enrichWithCitations<T extends { entry_id: string }>(
    papers: T[],
  ): Promise<(T & { citations: string[]; references: string[] })[]> {
    if (!papers.length) return [];

    const entryIds = papers.map((p) => p.entry_id);

    const [citRows, refRows] = await Promise.all([
      this.prisma.paperCitation.findMany({
        where: { belonging_paper_entry_id: { in: entryIds } },
        select: { belonging_paper_entry_id: true, cited_paper_entry_id: true },
      }),
      this.prisma.paperReference.findMany({
        where: { belonging_paper_entry_id: { in: entryIds } },
        select: {
          belonging_paper_entry_id: true,
          referenced_paper_entry_id: true,
        },
      }),
    ]);

    const citationMap = new Map<string, string[]>();
    for (const r of citRows) {
      const arr = citationMap.get(r.belonging_paper_entry_id);
      if (arr) arr.push(r.cited_paper_entry_id);
      else
        citationMap.set(r.belonging_paper_entry_id, [r.cited_paper_entry_id]);
    }

    const referenceMap = new Map<string, string[]>();
    for (const r of refRows) {
      const arr = referenceMap.get(r.belonging_paper_entry_id);
      if (arr) arr.push(r.referenced_paper_entry_id);
      else
        referenceMap.set(r.belonging_paper_entry_id, [
          r.referenced_paper_entry_id,
        ]);
    }

    return papers.map((p) => ({
      ...p,
      citations: citationMap.get(p.entry_id) ?? [],
      references: referenceMap.get(p.entry_id) ?? [],
    }));
  }
}

/**
 *
 * Konvertiert einen unbekannten Wert in eine endliche Zahl, wobei der angegebene Fallback zurückgegeben wird, wenn die Konvertierung nicht möglich ist.
 */
function toNumber(value: unknown, fallback: number): number {
  const parsed =
    typeof value === 'string' && value.trim() !== ''
      ? Number(value)
      : typeof value === 'number'
        ? value
        : NaN;

  if (Number.isFinite(parsed)) {
    return parsed;
  }
  return fallback;
}

function orderByFor(
  sort: PaperSort | undefined,
): Prisma.PaperOrderByWithRelationInput[] {
  switch (sort) {
    case 'citations':
      return [{ arxiv_citation_count: 'desc' }, { id: 'asc' }];
    case 'published_asc':
      return [{ published: { sort: 'asc', nulls: 'last' } }, { id: 'asc' }];
    default:
      return [{ published: { sort: 'desc', nulls: 'last' } }, { id: 'asc' }];
  }
}
