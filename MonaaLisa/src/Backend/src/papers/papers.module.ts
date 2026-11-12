import { Module } from '@nestjs/common';
import { PapersService } from './papers.service';
import { PapersController } from './papers.controller';
import { PrismaModule } from 'src/prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  controllers: [PapersController],
  providers: [PapersService],
  exports: [PapersService], // optional, falls andere Module den Service brauchen
})
export class PapersModule {}
