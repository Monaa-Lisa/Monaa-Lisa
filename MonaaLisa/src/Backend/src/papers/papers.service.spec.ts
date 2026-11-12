import { Test, TestingModule } from '@nestjs/testing';
import { DatabaseService } from '../database/database.service';
import { PapersService } from './papers.service';

describe('PapersService', () => {
  it('can be created with a database', async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [PapersService, { provide: DatabaseService, useValue: {} }],
    }).compile();

    expect(module.get(PapersService)).toBeDefined();
  });

  it('returns no papers for an empty id list without asking the database', async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [PapersService, { provide: DatabaseService, useValue: {} }],
    }).compile();

    await expect(module.get(PapersService).findByEntryIds([])).resolves.toEqual(
      [],
    );
  });
});
