/**
 * Nico August 2025
 */
import { Module } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaModule } from './prisma/prisma.module';
import { PapersModule } from './papers/papers.module';
import { PaperCitationsModule } from './paper-citations/paper-citations.module';
import { PaperReferencesModule } from './paper-references/paper-references.module';

// Request flow: Client -> Controller -> Service -> (DB) -> Service -> Controller -> Client
@Module({
  imports: [
    // Per-IP rate limit for the whole API. Opening a paper triggers a few
    // requests, so the default leaves room for normal browsing.
    ThrottlerModule.forRoot([
      {
        ttl: 60_000,
        limit: Number(process.env.RATE_LIMIT_PER_MINUTE ?? 300),
      },
    ]),
    // PrismaModule is global, so every service can inject PrismaService
    PrismaModule,
    PapersModule,
    PaperCitationsModule,
    PaperReferencesModule,
  ],
  controllers: [AppController],
  providers: [{ provide: APP_GUARD, useClass: ThrottlerGuard }, AppService],
})
export class AppModule {}
