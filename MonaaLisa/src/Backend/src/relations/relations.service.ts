import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateRelationDto } from './dto/create-relation.dto';

/**
 * RelationsService
 * -------------------------------
 * Kümmert sich um alles rund um "PaperRelation":
 * - Anlegen von Relationen zwischen Papers
 * - Abrufen von Relationen nach source_id oder target_id
 * - Löschen von Relationen
 */
@Injectable()
export class RelationsService {
  constructor(private prisma: PrismaService) {}

  /**
   * Legt eine neue Relation zwischen zwei Papers an.
   */
  async create(dto: CreateRelationDto) {
    return this.prisma.paperRelation.create({
      data: {
        source_id: dto.source_id,
        target_id: dto.target_id,
        confidence: dto.confidence,
      },
    });
  }

  /**
   * Upsert: Erstellt oder aktualisiert eine Relation.
   */
  async upsert(dto: CreateRelationDto) {
    return this.prisma.paperRelation.upsert({
      where: {
        source_id_target_id: {
          source_id: dto.source_id,
          target_id: dto.target_id,
        },
      },
      update: {
        confidence: dto.confidence,
      },
      create: {
        source_id: dto.source_id,
        target_id: dto.target_id,
        confidence: dto.confidence,
      },
    });
  }

  /**
   * Gibt alle Relationen zurück.
   */
  async findAll(take = 1000, skip = 0) {
    return this.prisma.paperRelation.findMany({
      take,
      skip,
      orderBy: { confidence: 'desc' },
    });
  }

  /**
   * Findet alle Relationen, bei denen das gegebene Paper die Quelle ist.
   */
  async findBySourceId(sourceId: string) {
    return this.prisma.paperRelation.findMany({
      where: { source_id: sourceId },
      orderBy: { confidence: 'desc' },
    });
  }

  /**
   * Findet alle Relationen, bei denen das gegebene Paper das Ziel ist.
   */
  async findByTargetId(targetId: string) {
    return this.prisma.paperRelation.findMany({
      where: { target_id: targetId },
      orderBy: { confidence: 'desc' },
    });
  }

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

  /**
   * Findet eine spezifische Relation.
   */
  async findOne(sourceId: string, targetId: string) {
    return this.prisma.paperRelation.findUnique({
      where: {
        source_id_target_id: {
          source_id: sourceId,
          target_id: targetId,
        },
      },
    });
  }

  /**
   * Löscht eine spezifische Relation.
   */
  async remove(sourceId: string, targetId: string) {
    return this.prisma.paperRelation.delete({
      where: {
        source_id_target_id: {
          source_id: sourceId,
          target_id: targetId,
        },
      },
    });
  }
}

