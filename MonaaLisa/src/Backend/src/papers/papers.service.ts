import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { Prisma } from '@prisma/client';
import { QueryPaperDto } from './dto/query-paper.dto';

/**
 * PapersService Nico
 * -------------------------------
 * Read access to papers: search, pagination, single and batch lookups.
 */
@Injectable()
export class PapersService {
  constructor(private prisma: PrismaService) {}

  /**
   * Filtert eine Liste von bekannten entry_ids nach den Kriterien aus der UI.
   * Das verhindert, dass wir zehntausende Paper ins Frontend laden müssen.
   */
  async findFilteredNeighbours(
    entryIds: string[],
    filter: {
      dateFrom?: string;
      dateTo?: string;
      authorQuery?: string;
      abstractQuery?: string;
      minCitations?: number;
      // onlyArxiv wird implizit behandelt, da non-arXiv Paper
      // oft eh nicht in der Haupt-Tabelle liegen oder keine validen Daten haben.
    },
  ) {
    if (!entryIds || entryIds.length === 0) return [];

    const where: Prisma.PaperWhereInput = {
      entry_id: { in: entryIds },
    };

    // 1. Datumsfilter
    if (filter.dateFrom || filter.dateTo) {
      const publishedFilter: Prisma.DateTimeNullableFilter = {};
      if (filter.dateFrom) publishedFilter.gte = new Date(filter.dateFrom);
      if (filter.dateTo) publishedFilter.lte = new Date(filter.dateTo);
      where.published = publishedFilter;
    }

    // 2. Autorenfilter (Case-Insensitive Suche in Prisma)
    if (filter.authorQuery && filter.authorQuery.trim() !== '') {
      where.authors = {
        contains: filter.authorQuery.trim(),
        mode: 'insensitive',
      };
    }

    // 3. Abstractfilter (Case-Insensitive Suche in Prisma)
    if (filter.abstractQuery && filter.abstractQuery.trim() !== '') {
      where.abstract = {
        contains: filter.abstractQuery.trim(),
        mode: 'insensitive',
      };
    }

    // 4. Minimum Citations
    if (filter.minCitations !== undefined && filter.minCitations >= 0) {
      where.non_arxiv_citation_count = {
        gte: filter.minCitations,
      };
    }

    // Wir holen nur die Felder, die die Sidebar wirklich braucht,
    // um Bandbreite und RAM zu sparen.
    const papers = await this.prisma.paper.findMany({
      where,
      select: {
        entry_id: true,
        title: true,
        authors: true,
        abstract: true,
        published: true,
        categories: true,
        non_arxiv_citation_count: true,
        non_arxiv_reference_count: true,
      },
      // Ein Limit als Sicherheitsgurt, falls ein Filter zu "weich" ist
      take: 1000,
    });

    return papers;
  }

  /**
   * Sucht Papers mit Volltext-Like über `title`, `authors`, `summary`,
   * plus optionaler Kategorie & Datumsbereich.
   * Pagination via `skip`/`take`, dazu Gesamtanzahl für UI.
   */
  // `MonaaLisa/src/Backend/src/papers/papers.service.ts`

  async findMany(q: QueryPaperDto) {
    const skip = toNumber(q.skip, 0);
    const take = toNumber(q.take, Math.pow(2, 31) - 1);

    // ── sort=citations → raw SQL path (order by citation count DESC) ──
    if (
      q.sort === 'citations' &&
      q.categories &&
      !q.search &&
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
        orderBy: [{ published: 'desc' }],
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
   * Optimised path: fetches papers for a category ordered by citation count.
   * Uses raw SQL because Prisma cannot ORDER BY a count from a joined table.
   */
  private async findManyByCitationCount(
    category: string,
    skip: number,
    take: number,
  ) {
    const papers: any[] = await this.prisma.$queryRaw`
      SELECT p.*,
             COALESCE(cc.cnt, 0) AS cit_count
        FROM paper p
        LEFT JOIN (
          SELECT belonging_paper_entry_id, COUNT(*) AS cnt
            FROM paper_citation
           GROUP BY belonging_paper_entry_id
        ) cc ON cc.belonging_paper_entry_id = p.entry_id
       WHERE p.categories LIKE ${'%' + category + '%'}
       ORDER BY cit_count DESC
       OFFSET ${skip}
        LIMIT ${take}
    `;

    const total: [{ count: bigint }] = await this.prisma.$queryRaw`
      SELECT COUNT(*) as count FROM paper
       WHERE categories LIKE ${'%' + category + '%'}
    `;

    // Raw query returns BigInt for count columns – convert to number
    const items = papers.map(({ cit_count, ...rest }) => ({
      ...rest,
      id: Number(rest.id),
      non_arxiv_citation_count:
        rest.non_arxiv_citation_count != null
          ? Number(rest.non_arxiv_citation_count)
          : null,
      non_arxiv_reference_count:
        rest.non_arxiv_reference_count != null
          ? Number(rest.non_arxiv_reference_count)
          : null,
    }));

    const enrichedItems = await this.enrichWithCitations(items as any);
    return { items: enrichedItems, total: Number(total[0].count), skip, take };
  }

  /**
   * Holt ein Paper per `entry_id`.
   * Wirft, wenn es die ID nicht gibt → bewusst, damit der Caller entscheiden kann.
   */
  async findByEntryId(entry_id: string) {
    const paper = await this.prisma.paper.findUniqueOrThrow({
      where: { entry_id },
    });
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
