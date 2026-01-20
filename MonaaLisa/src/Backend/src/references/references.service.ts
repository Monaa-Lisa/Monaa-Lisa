import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateReferenceDto } from './dto/create-reference.dto';

@Injectable()
export class ReferencesService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreateReferenceDto) {
    return this.prisma.reference.create({
      data: {
        belonging_paper_entry_id: dto.belonging_paper_entry_id,
        semanticscholar_obj: dto.semanticscholar_obj,
      },
    });
  }

  async findAll() {
    return this.prisma.reference.findMany();
  }

  async findByPaperEntryId(entryId: string) {
    return this.prisma.reference.findMany({
      where: { belonging_paper_entry_id: entryId },
    });
  }

  async findOne(id: number) {
    return this.prisma.reference.findUnique({
      where: { id },
    });
  }

  async remove(id: number) {
    return this.prisma.reference.delete({
      where: { id },
    });
  }
}

