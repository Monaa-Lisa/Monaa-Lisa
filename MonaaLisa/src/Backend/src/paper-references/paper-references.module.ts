import { Module } from '@nestjs/common';
import { PaperReferencesService } from './paper-references.service';
import { PaperReferencesController } from './paper-references.controller';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  controllers: [PaperReferencesController],
  providers: [PaperReferencesService],
  exports: [PaperReferencesService],
})
export class PaperReferencesModule {}

