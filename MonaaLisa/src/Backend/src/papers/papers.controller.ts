/**
 * Nico - August 2025
 *
 * PapersController
 * -------------------------------
 * Read-only REST endpoints for papers. Papers are written by the Python
 * pipeline directly into the database, so there are no write endpoints here.
 * Der Controller ist schlank gehalten und delegiert alles an den Service.
 * Validierung/Transformation passiert über die DTOs (class-validator / class-transformer).
 */
import { Body, Controller, Get, Param, Post, Query } from '@nestjs/common';
import { PapersService } from './papers.service';
import { QueryPaperDto } from './dto/query-paper.dto';

@Controller('papers')
export class PapersController {
  constructor(private readonly papers: PapersService) {}

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

  @Post('neighbours/filtered')
  async getNeighbours(@Body() body: { entryIds: string[]; filter: any }) {
    return this.papers.findFilteredNeighbours(body.entryIds, body.filter);
  }
}
