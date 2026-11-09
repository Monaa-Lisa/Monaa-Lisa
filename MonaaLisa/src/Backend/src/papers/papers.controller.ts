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
import {
  Body,
  Controller,
  DefaultValuePipe,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Query,
} from '@nestjs/common';
import { DEFAULT_SIMILAR, PapersService } from './papers.service';
import { BatchPapersDto, QueryPaperDto } from './dto';

@Controller('papers')
export class PapersController {
  constructor(private readonly papers: PapersService) {}

  /**
   * POST /papers/batch
   * Batch-Fetch: holt mehrere Papers anhand einer Liste von `entry_id`s.
   */
  @Post('batch')
  findBatch(@Body() body: BatchPapersDto) {
    return this.papers.findByEntryIds(body.entryIds);
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
   * GET /papers/count
   * How many papers match the same filters as GET /papers: { total }
   */
  @Get('count')
  async count(@Query() q: QueryPaperDto) {
    return { total: await this.papers.count(q) };
  }

  /**
   * GET /papers/years
   * First and last year of publication in the dataset: { first, last }
   */
  @Get('years')
  years() {
    return this.papers.years();
  }

  /**
   * GET /papers/:entryId/similar
   * The papers nearest to one paper: { basis, items }, see the service.
   */
  @Get(':entryId/similar')
  similar(
    @Param('entryId') entryId: string,
    @Query('take', new DefaultValuePipe(DEFAULT_SIMILAR), ParseIntPipe)
    take: number,
  ) {
    return this.papers.similarTo(entryId, take);
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
}
