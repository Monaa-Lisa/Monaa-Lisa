import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { Prisma } from '@prisma/client';

@Injectable()
export class EmbeddingsService {
  constructor(private readonly prisma: PrismaService) {}

  /** Upsert für ein Paper-Embedding (keyed by belonging_paper_entry_id) 
   *  Using raw SQL because Prisma Client doesn't support writing to Unsupported types directly.
   */
  async upsert(entryId: string, vector: number[]) {
    // Format vector as string for pgvector: "[1.0, 2.0, ...]"
    const vectorString = JSON.stringify(vector);

    // Use raw query for upsert
    // Note: '::vector' cast is important for Postgres to treat it as vector type
    return this.prisma.$executeRaw`
      INSERT INTO "embedding" ("belonging_paper_entry_id", "content")
      VALUES (${entryId}, ${vectorString}::vector)
      ON CONFLICT ("belonging_paper_entry_id") 
      DO UPDATE SET "content" = ${vectorString}::vector;
    `;
  }

  /** Ein Embedding holen */
  get(entryId: string) {
    // Reading works fine with findUnique if we don't need the vector content
    // BUT if you need the vector content, you also need raw query to cast it back to text or json
    // likely. For now user didn't ask to change reading, but reading Unsupported fields
    // is also tricky. 
    // However, usually we just need to confirm it exists or get ID.
    return this.prisma.embedding.findUnique({
      where: { belonging_paper_entry_id: entryId },
    });
  }

  /** Embedding löschen (idempotent via deleteIfExists) */
  async remove(entryId: string) {
    try {
      await this.prisma.embedding.delete({
        where: { belonging_paper_entry_id: entryId },
      });
       return { deleted: true };
    } catch {
      return { deleted: false }; // nicht gefunden → ok
    }
  }
}
