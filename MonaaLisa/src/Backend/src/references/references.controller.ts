import { Controller, Get, Post, Body, Param, Delete } from '@nestjs/common';
import { ReferencesService } from './references.service';
import { CreateReferenceDto } from './dto/create-reference.dto';

@Controller('references')
export class ReferencesController {
  constructor(private readonly referencesService: ReferencesService) {}

  @Post()
  create(@Body() createReferenceDto: CreateReferenceDto) {
    return this.referencesService.create(createReferenceDto);
  }

  @Get()
  findAll() {
    return this.referencesService.findAll();
  }

  @Get('paper/:entryId')
  findByPaperEntryId(@Param('entryId') entryId: string) {
    return this.referencesService.findByPaperEntryId(entryId);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.referencesService.findOne(+id);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.referencesService.remove(+id);
  }
}

