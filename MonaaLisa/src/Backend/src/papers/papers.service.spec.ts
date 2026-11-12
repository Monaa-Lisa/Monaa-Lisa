/**
 * Nico & Nick August 2025
 *
 * Ziel dieses Specs:
 * - "Smoke Test": Lädt das TestingModule und stellt sicher, dass der Service existiert.
 * - Hinweis: PapersService injiziert PrismaService
 */
import { Test, TestingModule } from '@nestjs/testing';
import { PapersService } from './papers.service';

describe('PaperService', () => {
  let service: PapersService;

  beforeEach(async () => {
    // Minimal-Variante (ohne Mock) – Provoziert DI-Fehler bewusst.
    const module: TestingModule = await Test.createTestingModule({
      providers: [PapersService],
    }).compile();

    service = module.get<PapersService>(PapersService);
  });

  it('should be defined', () => {
    // bestätigt, dass DI/Module grundsätzlich passt
    expect(service).toBeDefined();
  });
});
