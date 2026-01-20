import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateCitationDto } from './dto/create-citation.dto';

@Injectable()
export class CitationsService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreateCitationDto) {
    return this.prisma.citation.create({
      data: {
        belonging_paper_entry_id: dto.belonging_paper_entry_id,
        semanticscholar_obj: dto.semanticscholar_obj,
      },
    });
  }

  async findAll() {
    return this.prisma.citation.findMany();
  }

  async findByPaperEntryId(entryId: string) {
    return this.prisma.citation.findMany({
      where: { belonging_paper_entry_id: entryId },
    });
  }

  async findOne(id: number) {
    return this.prisma.citation.findUnique({
      where: { id },
    });
  }

  async remove(id: number) {
    return this.prisma.citation.delete({
      where: { id },
    });
  }
}

