import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class ReferencesService {
  constructor(private prisma: PrismaService) {}

  async findByPaperEntryId(entryId: string) {
    return this.prisma.reference.findMany({
      where: { belonging_paper_entry_id: entryId },
    });
  }
}

