import { Controller, Get, Param } from '@nestjs/common';
import { PaperReferencesService } from './paper-references.service';

@Controller('paper-references')
export class PaperReferencesController {
  constructor(private readonly paperReferencesService: PaperReferencesService) {}

  @Get('paper/:entryId')
  findByBelongingPaper(@Param('entryId') entryId: string) {
    return this.paperReferencesService.findByBelongingPaper(entryId);
  }
}

