import { Module } from '@nestjs/common';
import { CitationsService } from './citations.service';
import { CitationsController } from './citations.controller';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  controllers: [CitationsController],
  providers: [CitationsService],
  exports: [CitationsService],
})
export class CitationsModule {}

