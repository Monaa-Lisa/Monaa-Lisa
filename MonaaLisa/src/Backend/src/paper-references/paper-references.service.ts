import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreatePaperReferenceDto } from './dto/create-paper-reference.dto';

@Injectable()
export class PaperReferencesService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreatePaperReferenceDto) {
    return this.prisma.paperReference.create({
      data: {
        belonging_paper_entry_id: dto.belonging_paper_entry_id,
        referenced_paper_entry_id: dto.referenced_paper_entry_id,
      },
    });
  }

  async findAll() {
    return this.prisma.paperReference.findMany();
  }

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

  async remove(belonging_paper_entry_id: string, referenced_paper_entry_id: string) {
    return this.prisma.paperReference.delete({
      where: {
        belonging_paper_entry_id_referenced_paper_entry_id: {
          belonging_paper_entry_id,
          referenced_paper_entry_id,
        },
      },
    });
  }
}

