import { Controller, Get, Param } from '@nestjs/common';
import { PaperCitationsService } from './paper-citations.service';

@Controller('paper-citations')
export class PaperCitationsController {
  constructor(private readonly paperCitationsService: PaperCitationsService) {}

  @Get('paper/:entryId')
  findByBelongingPaper(@Param('entryId') entryId: string) {
    return this.paperCitationsService.findByBelongingPaper(entryId);
  }
}

