import { Module } from '@nestjs/common';
import { PaperCitationsService } from './paper-citations.service';
import { PaperCitationsController } from './paper-citations.controller';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  controllers: [PaperCitationsController],
  providers: [PaperCitationsService],
  exports: [PaperCitationsService],
})
export class PaperCitationsModule {}

