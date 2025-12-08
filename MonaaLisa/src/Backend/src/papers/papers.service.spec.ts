/**
 * Nico & Nick August 2025
 *
 * Ziel dieses Specs:
 * - "Smoke Test": Lädt das TestingModule und stellt sicher, dass der Service existiert.
 * - Hinweis: PapersService injiziert PrismaService
 */
import { Test, TestingModule } from '@nestjs/testing';
import { PapersService } from './papers.service';
import { PrismaService } from '../prisma/prisma.service';

const createPrismaMock = () => {
  const paperApi = {
    create: jest.fn(),
    upsert: jest.fn(),
    findMany: jest.fn(),
    count: jest.fn(),
    findUniqueOrThrow: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  };

  return {
    paper: paperApi,
    $transaction: jest
      .fn()
      .mockImplementation(async (operations: Array<Promise<unknown>>) =>
        Promise.all(operations),
      ),
  };
};

describe('PaperService', () => {
  let service: PapersService;
  let prismaMock: ReturnType<typeof createPrismaMock>;

  beforeEach(async () => {
    prismaMock = createPrismaMock();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PapersService,
        {
          provide: PrismaService,
          useValue: prismaMock,
        },
      ],
    }).compile();

    service = module.get<PapersService>(PapersService);
  });

  it('should be defined', () => {
    // bestätigt, dass DI/Module grundsätzlich passt
    expect(service).toBeDefined();
  });

  it('creates a paper with normalized payload', async () => {
    const dto = {
      entry_id: 'arXiv:1234',
      title: 'Test',
      authors: 'A, B',
      summary: 'Summary',
      published: '2024-01-01T00:00:00Z',
      category: 'cs.AI',
      url: 'https://example.com',
      hash: 'hash',
    };

    const created = { id: 1, ...dto } as unknown;
    prismaMock.paper.create.mockResolvedValue(created);

    const result = await service.create(dto as never);

    expect(prismaMock.paper.create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        entry_id: dto.entry_id,
        published: new Date(dto.published),
        added: expect.any(Date),
      }),
    });
    expect(result).toBe(created);
  });

  it('performs an upsert by entry id', async () => {
    const dto = {
      entry_id: 'arXiv:9999',
      title: 'Updated',
      authors: 'A',
      summary: 'S',
      hash: 'hash',
    };

    prismaMock.paper.upsert.mockResolvedValue({ id: 2 });

    await service.upsertByEntryId(dto as never);

    expect(prismaMock.paper.upsert).toHaveBeenCalledWith({
      where: { entry_id: dto.entry_id },
      update: expect.objectContaining({ title: dto.title }),
      create: expect.objectContaining({ entry_id: dto.entry_id }),
    });
  });

  it('delegates delete to prisma', async () => {
    prismaMock.paper.delete.mockResolvedValue({});

    await service.deleteByEntryId('arXiv:remove');

    expect(prismaMock.paper.delete).toHaveBeenCalledWith({
      where: { entry_id: 'arXiv:remove' },
    });
  });
});
