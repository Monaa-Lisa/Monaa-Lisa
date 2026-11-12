/**
 * Nico August 2025
 */
import { Controller, Get, ServiceUnavailableException } from '@nestjs/common';
import { SkipThrottle } from '@nestjs/throttler';
import { DatabaseService } from './database/database.service';

@Controller()
export class AppController {
  constructor(private readonly db: DatabaseService) {}

  /**
   * GET /health
   * Used by the docker healthcheck, so it is not rate limited.
   * Answers 503 when the database cannot be reached.
   */
  @SkipThrottle()
  @Get('health')
  async health() {
    try {
      await this.db.ping();
    } catch {
      throw new ServiceUnavailableException({ status: 'error', db: 'down' });
    }
    return { status: 'ok' };
  }
}
