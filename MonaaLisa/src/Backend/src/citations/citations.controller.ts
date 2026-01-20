import { Controller, Get, Post, Body, Param, Delete } from '@nestjs/common';
import { CitationsService } from './citations.service';
import { CreateCitationDto } from './dto/create-citation.dto';

@Controller('citations')
export class CitationsController {
  constructor(private readonly citationsService: CitationsService) {}

  @Post()
  create(@Body() createCitationDto: CreateCitationDto) {
    return this.citationsService.create(createCitationDto);
  }

  @Get()
  findAll() {
    return this.citationsService.findAll();
  }

  @Get('paper/:entryId')
  findByPaperEntryId(@Param('entryId') entryId: string) {
    return this.citationsService.findByPaperEntryId(entryId);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.citationsService.findOne(+id);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.citationsService.remove(+id);
  }
}

