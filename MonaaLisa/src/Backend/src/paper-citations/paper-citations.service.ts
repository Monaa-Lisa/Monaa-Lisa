import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreatePaperCitationDto } from './dto/create-paper-citation.dto';

@Injectable()
export class PaperCitationsService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreatePaperCitationDto) {
    return this.prisma.paperCitation.create({
      data: {
        belonging_paper_entry_id: dto.belonging_paper_entry_id,
        cited_paper_entry_id: dto.cited_paper_entry_id,
      },
    });
  }

  async findAll() {
    return this.prisma.paperCitation.findMany();
  }

  async findByBelongingPaper(entryId: string) {
    return this.prisma.paperCitation.findMany({
      where: { belonging_paper_entry_id: entryId },
    });
  }

  // To remove a link we need both keys
  async remove(belonging_paper_entry_id: string, cited_paper_entry_id: string) {
    return this.prisma.paperCitation.delete({
      where: {
        belonging_paper_entry_id_cited_paper_entry_id: {
          belonging_paper_entry_id,
          cited_paper_entry_id,
        },
      },
    });
  }
}

