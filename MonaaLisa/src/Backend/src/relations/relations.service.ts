import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

/**
 * RelationsService
 * -------------------------------
 * Kümmert sich um alles rund um "PaperRelation":
 * - Abrufen von Relationen für ein Paper
 */
@Injectable()
export class RelationsService {
  constructor(private prisma: PrismaService) {}

  /**
   * Findet alle Relationen für ein Paper (sowohl als Quelle als auch als Ziel).
   */
  async findByPaperId(entryId: string) {
    return this.prisma.paperRelation.findMany({
      where: {
        OR: [
          { source_id: entryId },
          { target_id: entryId },
        ],
      },
      orderBy: { confidence: 'desc' },
    });
  }
}

