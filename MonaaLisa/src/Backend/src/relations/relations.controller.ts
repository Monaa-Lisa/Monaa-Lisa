/**
 * RelationsController
 * -------------------------------
 * REST-Endpunkte rund um "PaperRelation".
 * Stellt Relationen zwischen Papers dar (z.B. Ähnlichkeit, Verwandtschaft).
 */
import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Query,
} from '@nestjs/common';
import { RelationsService } from './relations.service';
import { CreateRelationDto } from './dto/create-relation.dto';

@Controller('relations')
export class RelationsController {
  constructor(private readonly relations: RelationsService) {}

  /**
   * POST /relations
   * Legt eine neue Relation an.
   */
  @Post()
  create(@Body() dto: CreateRelationDto) {
    return this.relations.create(dto);
  }

  /**
   * POST /relations/upsert
   * Idempotente Ingestion: legt an oder aktualisiert anhand source_id/target_id.
   */
  @Post('upsert')
  upsert(@Body() dto: CreateRelationDto) {
    return this.relations.upsert(dto);
  }

  /**
   * GET /relations
   * Listet alle Relationen mit optionaler Pagination.
   */
  @Get()
  findAll(
    @Query('take') take?: string,
    @Query('skip') skip?: string,
  ) {
    return this.relations.findAll(
      take ? parseInt(take, 10) : 1000,
      skip ? parseInt(skip, 10) : 0,
    );
  }

  /**
   * GET /relations/source/:sourceId
   * Findet alle Relationen, bei denen das gegebene Paper die Quelle ist.
   */
  @Get('source/:sourceId')
  findBySourceId(@Param('sourceId') sourceId: string) {
    return this.relations.findBySourceId(sourceId);
  }

  /**
   * GET /relations/target/:targetId
   * Findet alle Relationen, bei denen das gegebene Paper das Ziel ist.
   */
  @Get('target/:targetId')
  findByTargetId(@Param('targetId') targetId: string) {
    return this.relations.findByTargetId(targetId);
  }

  /**
   * GET /relations/paper/:entryId
   * Findet alle Relationen für ein Paper (sowohl als Quelle als auch als Ziel).
   */
  @Get('paper/:entryId')
  findByPaperId(@Param('entryId') entryId: string) {
    return this.relations.findByPaperId(entryId);
  }

  /**
   * GET /relations/:sourceId/:targetId
   * Findet eine spezifische Relation.
   */
  @Get(':sourceId/:targetId')
  findOne(
    @Param('sourceId') sourceId: string,
    @Param('targetId') targetId: string,
  ) {
    return this.relations.findOne(sourceId, targetId);
  }

  /**
   * DELETE /relations/:sourceId/:targetId
   * Löscht eine spezifische Relation.
   */
  @Delete(':sourceId/:targetId')
  remove(
    @Param('sourceId') sourceId: string,
    @Param('targetId') targetId: string,
  ) {
    return this.relations.remove(sourceId, targetId);
  }
}

