import { Controller, Get, Post, Body, Param, Delete } from '@nestjs/common';
import { PaperReferencesService } from './paper-references.service';
import { CreatePaperReferenceDto } from './dto/create-paper-reference.dto';

@Controller('paper-references')
export class PaperReferencesController {
  constructor(private readonly paperReferencesService: PaperReferencesService) {}

  @Post()
  create(@Body() createDto: CreatePaperReferenceDto) {
    return this.paperReferencesService.create(createDto);
  }

  @Get()
  findAll() {
    return this.paperReferencesService.findAll();
  }

  @Get('paper/:entryId')
  findByBelongingPaper(@Param('entryId') entryId: string) {
    return this.paperReferencesService.findByBelongingPaper(entryId);
  }

  @Delete(':belongingId/:referencedId')
  remove(
    @Param('belongingId') belongingId: string,
    @Param('referencedId') referencedId: string,
  ) {
    return this.paperReferencesService.remove(belongingId, referencedId);
  }
}

