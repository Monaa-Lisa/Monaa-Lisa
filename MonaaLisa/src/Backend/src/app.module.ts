/**
 * Nico August 2025
 */
import { Module } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { AppController } from './app.controller';
import { DatabaseModule } from './database/database.module';
import { PapersModule } from './papers/papers.module';
import { EdgesModule } from './edges/edges.module';
import { CategoriesModule } from './categories/categories.module';

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
    // global, every service can inject DatabaseService
    DatabaseModule,
    PapersModule,
    EdgesModule,
    CategoriesModule,
  ],
  controllers: [AppController],
  providers: [{ provide: APP_GUARD, useClass: ThrottlerGuard }],
})
export class AppModule {}
