import { Controller, Get, Param } from '@nestjs/common';
import { ReferencesService } from './references.service';

@Controller('references')
export class ReferencesController {
  constructor(private readonly referencesService: ReferencesService) {}

  @Get('paper/:entryId')
  findByPaperEntryId(@Param('entryId') entryId: string) {
    return this.referencesService.findByPaperEntryId(entryId);
  }
}

