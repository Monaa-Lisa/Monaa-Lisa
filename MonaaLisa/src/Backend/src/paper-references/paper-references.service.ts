import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class PaperReferencesService {
  constructor(private prisma: PrismaService) {}

  async findByBelongingPaper(entryId: string) {
    // Get all references for this paper
    const references = await this.prisma.paperReference.findMany({
      where: { belonging_paper_entry_id: entryId },
    });

    // Filter out references where the referenced paper has a stub title
    const referencedPaperIds = references.map((r) => r.referenced_paper_entry_id);
    const validPapers = await this.prisma.paper.findMany({
      where: {
        entry_id: { in: referencedPaperIds },
        title: { not: '[STUB] Pending Fetch' },
      },
      select: { entry_id: true },
    });

    const validEntryIds = new Set(validPapers.map((p) => p.entry_id));
    return references.filter((r) => validEntryIds.has(r.referenced_paper_entry_id));
  }
}

