import { ServiceUnavailableException } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { AppController } from './app.controller';
import { DatabaseService } from './database/database.service';

describe('AppController', () => {
  const db = { ping: jest.fn() };
  let controller: AppController;

  beforeEach(async () => {
    db.ping.mockReset();
    const module: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [{ provide: DatabaseService, useValue: db }],
    }).compile();

    controller = module.get(AppController);
  });

  it('reports ok when the database answers', async () => {
    db.ping.mockResolvedValue(undefined);
    await expect(controller.health()).resolves.toEqual({ status: 'ok' });
  });

  it('answers 503 when the database is down', async () => {
    db.ping.mockRejectedValue(new Error('connection refused'));
    await expect(controller.health()).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );
  });
});
