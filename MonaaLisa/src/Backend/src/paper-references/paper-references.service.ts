import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreatePaperReferenceDto } from './dto/create-paper-reference.dto';

@Injectable()
export class PaperReferencesService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreatePaperReferenceDto) {
    return this.prisma.paperReference.create({
      data: {
        belonging_paper_entry_id: dto.belonging_paper_entry_id,
        referenced_paper_entry_id: dto.referenced_paper_entry_id,
      },
    });
  }

  async findAll() {
    return this.prisma.paperReference.findMany();
  }

  async findByBelongingPaper(entryId: string) {
    return this.prisma.paperReference.findMany({
      where: { belonging_paper_entry_id: entryId },
    });
  }

  async remove(belonging_paper_entry_id: string, referenced_paper_entry_id: string) {
    return this.prisma.paperReference.delete({
      where: {
        belonging_paper_entry_id_referenced_paper_entry_id: {
          belonging_paper_entry_id,
          referenced_paper_entry_id,
        },
      },
    });
  }
}

