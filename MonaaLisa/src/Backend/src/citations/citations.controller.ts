import { Controller, Get, Param } from '@nestjs/common';
import { CitationsService } from './citations.service';

@Controller('citations')
export class CitationsController {
  constructor(private readonly citationsService: CitationsService) {}

  @Get('paper/:entryId')
  findByPaperEntryId(@Param('entryId') entryId: string) {
    return this.citationsService.findByPaperEntryId(entryId);
  }
}

