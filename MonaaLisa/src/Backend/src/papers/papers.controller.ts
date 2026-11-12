/**
 * Nico - August 2025
 *
 * PapersController
 * -------------------------------
 * REST-Endpunkte rund um "Paper".
 * Der Controller ist schlank gehalten und delegiert alles an den Service.
 * Validierung/Transformation passiert über die DTOs (class-validator / class-transformer).
 */
import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import { PapersService } from './papers.service';
import { CreatePaperDto } from './dto/create-paper.dto';
import { UpdatePaperDto } from './dto/update-paper.dto';
import { QueryPaperDto } from './dto/query-paper.dto';

@Controller('papers')
export class PapersController {
  constructor(private readonly papers: PapersService) {}

  /**
   * POST /papers
   * Legt ein neues Paper an.
   *
   * Erwartet: CreatePaperDto im Body.
   * Hinweis: Standard-HTTP-Code für POST ist 201 (Created), sofern nicht überschrieben.
   */
  @Post()
  create(@Body() dto: CreatePaperDto) {
    return this.papers.create(dto);
  }

  /**
   * POST /papers/upsert
   * Idempotente Ingestion: legt an oder aktualisiert anhand `entry_id`.
   *
   * Use-Case: Feeds/Importer, die dasselbe Item mehrfach sehen können.
   */
  @Post('upsert')
  upsert(@Body() dto: CreatePaperDto) {
    return this.papers.upsertByEntryId(dto);
  }

  /**
   * POST /papers/batch
   * Batch-Fetch: holt mehrere Papers anhand einer Liste von `entry_id`s.
   */
  @Post('batch')
  findBatch(@Body() body: { entryIds: string[] }) {
    return this.papers.findByEntryIds(body.entryIds ?? []);
  }

  // Nick - November 2025
  // Die Möglichkeiten mehrere Papers zu finden und anschließend im FE zu filtern soll gegeben sein
  /**
   * GET /papers
   * Listet Papers mit Suche, Filtern und Pagination.
   *
   * Query-Parameter (QueryPaperDto):
   * - search: Volltext-like über title/authors/summary
   * - category: exakter Match
   * - dateFrom/dateTo: Datumsbereich (published)
   * - skip/take: Pagination
   *
   * Rückgabe: { items, total, skip, take }
   */
  @Get()
  findMany(@Query() q: QueryPaperDto) {
    return this.papers.findMany(q);
  }

  /**
   * GET /papers/:entryId
   * Holt ein einzelnes Paper anhand der externen `entryId`.
   * Achtung: Das ist die externe ID (z.B. aus dem Feed), nicht die DB-Primär-ID.
   */
  @Get(':entryId')
  findOne(@Param('entryId') entryId: string) {
    return this.papers.findByEntryId(entryId);
  }

  /**
   * PATCH /papers/:entryId
   * Aktualisiert Felder eines Papers.
   *
   * Verhalten:
   * - Nur übergebene Felder werden geändert.
   * - `published` wird nur gesetzt, wenn im DTO vorhanden.
   */
  @Patch(':entryId')
  update(@Param('entryId') entryId: string, @Body() dto: UpdatePaperDto) {
    return this.papers.updateByEntryId(entryId, dto);
  }

  @Post('neighbours/filtered')
  async getNeighbours(@Body() body: { entryIds: string[]; filter: any }) {
    return this.papers.findFilteredNeighbours(body.entryIds, body.filter);
  }

  // Nick - November 2025
  // Die Möglichkeiten ein paper zu löschen damit es neugeladen werden kann
  /**
   * DELETE /papers/:entryId
   * Löscht ein Paper.
   */
  @Delete(':entryId')
  remove(@Param('entryId') entryId: string) {
    return this.papers.deleteByEntryId(entryId);
  }
}
