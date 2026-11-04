/**
 * Nico August 2025
 */
import { Module } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaService } from './prisma/prisma.service';
import { PrismaModule } from './prisma/prisma.module';
import { PapersModule } from './papers/papers.module';
import { PapersService } from './papers/papers.service';
import { EmbeddingsService } from './embeddings/embeddings.service';
import { ReferencesModule } from './references/references.module';
import { CitationsModule } from './citations/citations.module';
import { PaperCitationsModule } from './paper-citations/paper-citations.module';
import { PaperReferencesModule } from './paper-references/paper-references.module';
import { RelationsModule } from './relations/relations.module';

// Das ist unser Modul. Module enthalten Struktur aber keinen Code selbst.
// Der typische ablauf ist Client->Controller->Service->(DB)->Service->Controller->Client
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
    PrismaModule,
    PapersModule,
    ReferencesModule,
    CitationsModule,
    PaperCitationsModule,
    PaperReferencesModule,
    RelationsModule,
  ], // andere @Module die intern benötigt werdfen
  controllers: [AppController], // Alle Controller die dem Modul zugeordnet sind. Nimmt Requests an
  providers: [
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    AppService,
    PrismaService,
    PapersService,
    EmbeddingsService,
  ], // Logik. Verwendet Datenbanken, Validierung usw. Wird vom Controller aufgerufen
})
export class AppModule {}
