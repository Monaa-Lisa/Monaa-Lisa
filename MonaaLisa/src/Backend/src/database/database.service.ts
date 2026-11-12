import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Kysely, PostgresDialect, sql } from 'kysely';
import { Pool } from 'pg';
import type { DB } from './schema';

/**
 * Typed query builder for the database (Kysely). The table types in
 * schema.ts are generated from the real database, see `npm run db:types`.
 * The schema itself is owned by the SQL migrations in /db/migrations.
 */
@Injectable()
export class DatabaseService extends Kysely<DB> implements OnModuleDestroy {
  constructor() {
    super({
      dialect: new PostgresDialect({
        pool: new Pool({ connectionString: process.env.DATABASE_URL }),
      }),
    });
  }

  /** Throws when the database cannot be reached */
  async ping(): Promise<void> {
    await sql`SELECT 1`.execute(this);
  }

  async onModuleDestroy() {
    await this.destroy();
  }
}
