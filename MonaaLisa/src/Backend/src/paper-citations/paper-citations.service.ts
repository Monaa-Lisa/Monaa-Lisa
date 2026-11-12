import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class PaperCitationsService {
  constructor(private prisma: PrismaService) {}

  async findByBelongingPaper(entryId: string) {
    // Get all citations for this paper
    const citations = await this.prisma.paperCitation.findMany({
      where: { belonging_paper_entry_id: entryId },
    });

    // Filter out citations where the cited paper has a stub title
    const citedPaperIds = citations.map((c) => c.cited_paper_entry_id);
    const validPapers = await this.prisma.paper.findMany({
      where: {
        entry_id: { in: citedPaperIds },
        title: { not: '[STUB] Pending Fetch' },
      },
      select: { entry_id: true },
    });

    const validEntryIds = new Set(validPapers.map((p) => p.entry_id));
    return citations.filter((c) => validEntryIds.has(c.cited_paper_entry_id));
  }
}
