import { Module } from '@nestjs/common';
import { PapersService } from './papers.service';
import { PapersController } from './papers.controller';

@Module({
  controllers: [PapersController],
  providers: [PapersService],
})
export class PapersModule {}
