import { Controller, Get, Post, Body, Param, Delete } from '@nestjs/common';
import { PaperCitationsService } from './paper-citations.service';
import { CreatePaperCitationDto } from './dto/create-paper-citation.dto';

@Controller('paper-citations')
export class PaperCitationsController {
  constructor(private readonly paperCitationsService: PaperCitationsService) {}

  @Post()
  create(@Body() createDto: CreatePaperCitationDto) {
    return this.paperCitationsService.create(createDto);
  }

  @Get()
  findAll() {
    return this.paperCitationsService.findAll();
  }

  @Get('paper/:entryId')
  findByBelongingPaper(@Param('entryId') entryId: string) {
    return this.paperCitationsService.findByBelongingPaper(entryId);
  }

  @Delete(':belongingId/:citedId')
  remove(
    @Param('belongingId') belongingId: string,
    @Param('citedId') citedId: string,
  ) {
    return this.paperCitationsService.remove(belongingId, citedId);
  }
}

