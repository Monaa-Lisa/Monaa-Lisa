/**
 * RelationsController
 * -------------------------------
 * REST-Endpunkte rund um "PaperRelation".
 * Stellt Relationen zwischen Papers dar (z.B. Ähnlichkeit, Verwandtschaft).
 */
import {
  Controller,
  Get,
  Param,
} from '@nestjs/common';
import { RelationsService } from './relations.service';

@Controller('relations')
export class RelationsController {
  constructor(private readonly relations: RelationsService) {}

  /**
   * GET /relations/paper/:entryId
   * Findet alle Relationen für ein Paper (sowohl als Quelle als auch als Ziel).
   */
  @Get('paper/:entryId')
  findByPaperId(@Param('entryId') entryId: string) {
    return this.relations.findByPaperId(entryId);
  }
}

