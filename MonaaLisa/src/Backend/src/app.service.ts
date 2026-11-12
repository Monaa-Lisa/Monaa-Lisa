/**
 * Nico August 2025
 */
import { Injectable } from '@nestjs/common';

@Injectable()
export class AppService {
  getHello(): string {
    return 'Hello from MonaaLisa!';
  }
}
