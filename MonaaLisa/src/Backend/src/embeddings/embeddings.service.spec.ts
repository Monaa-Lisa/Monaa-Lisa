import { Test, TestingModule } from '@nestjs/testing';
import { EmbeddingsService } from './embeddings.service';
import { PrismaService } from '../prisma/prisma.service';

const createPrismaMock = () => ({
  embedding: {
    upsert: jest.fn(),
    findUnique: jest.fn(),
    delete: jest.fn(),
  },
});

describe('EmbeddingsService', () => {
  let service: EmbeddingsService;
  let prismaMock: ReturnType<typeof createPrismaMock>;

  beforeEach(async () => {
    prismaMock = createPrismaMock();
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        EmbeddingsService,
        {
          provide: PrismaService,
          useValue: prismaMock,
        },
      ],
    }).compile();

    service = module.get<EmbeddingsService>(EmbeddingsService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  it('upserts an embedding', async () => {
    prismaMock.embedding.upsert.mockResolvedValue({ id: 1 });

    await service.upsert('paper-1', { vector: [0.1] });

    expect(prismaMock.embedding.upsert).toHaveBeenCalledWith({
      where: { belonging_paper_entry_id: 'paper-1' },
      update: { content: { vector: [0.1] } },
      create: {
        belonging_paper_entry_id: 'paper-1',
        content: { vector: [0.1] },
      },
    });
  });

  it('returns a single embedding', async () => {
    prismaMock.embedding.findUnique.mockResolvedValue({ id: 1 });

    const result = await service.get('paper-1');

    expect(result).toEqual({ id: 1 });
    expect(prismaMock.embedding.findUnique).toHaveBeenCalledWith({
      where: { belonging_paper_entry_id: 'paper-1' },
    });
  });

  it('removes an embedding gracefully when missing', async () => {
    prismaMock.embedding.delete.mockRejectedValue(new Error('not found'));

    const status = await service.remove('missing');

    expect(status).toEqual({ deleted: false });
  });
});
