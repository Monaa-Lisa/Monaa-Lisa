/**
 * The paper and citation endpoints against a real Postgres.
 *
 * Needs a throwaway database with the migrations applied (see the README).
 * The tests empty the paper tables and fill in their own rows, so they refuse
 * to run unless the database name ends in "_test".
 */
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { App } from 'supertest/types';
import { AppModule } from './../src/app.module';
import { DatabaseService } from './../src/database/database.service';

const databaseName = new URL(
  process.env.DATABASE_URL ?? 'postgres://localhost/none',
).pathname.slice(1);
const describeWithTestDb = databaseName.endsWith('_test')
  ? describe
  : describe.skip;

interface PaperRow {
  entry_id: string;
  title: string;
  abstract?: string;
}
interface Page {
  items: (PaperRow & Record<string, unknown>)[];
  total: number | null;
}

describeWithTestDb('papers and citations (e2e)', () => {
  let app: INestApplication<App>;
  let db: DatabaseService;

  const paper = (
    entry_id: string,
    title: string,
    arxiv: number,
    elsewhere: number | null,
    extra: {
      authors?: string;
      categories?: string;
      published?: string;
      abstract?: string;
    } = {},
  ) => ({
    entry_id,
    title,
    authors: extra.authors ?? 'Ada Lovelace',
    abstract: extra.abstract ?? `Abstract of ${title}`,
    categories: extra.categories ?? 'cs.LG',
    published: new Date(extra.published ?? '2015-01-01'),
    arxiv_citation_count: arxiv,
    non_arxiv_citation_count: elsewhere,
    tsne: JSON.stringify({ x: 1, y: 2, method: 'umap' }),
  });

  beforeAll(async () => {
    const module = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = module.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({ transform: true, whitelist: true }),
    );
    await app.init();
    db = app.get(DatabaseService);

    await db.deleteFrom('paper_citation').execute();
    await db.deleteFrom('paper_reference').execute();
    await db.deleteFrom('paper').execute();
    await db
      .insertInto('paper')
      .values([
        paper('1000.0001', 'Optimisers for deep networks', 2, 100),
        paper('1000.0002', 'A survey of optimisers', 0, 500, {
          categories: 'stat.ML cs.LG',
          published: '2018-06-01',
          abstract: 'We compare schedules for training.',
        }),
        paper('1000.0003', 'Faster training', 5, null, {
          authors: 'Grace Hopper',
          published: '2019-03-01',
        }),
        paper('1000.0004', '100% coverage of quantum fields', 0, 1, {
          categories: 'hep-th',
          published: '2010-01-01',
        }),
      ])
      .execute();
    // 0001 is cited by 0002 and 0003. The citation table only knows 0003 and
    // a paper that is not in the database, the rest comes from the references.
    await db
      .insertInto('paper_citation')
      .values([
        {
          belonging_paper_entry_id: '1000.0001',
          cited_paper_entry_id: '1000.0003',
        },
        {
          belonging_paper_entry_id: '1000.0001',
          cited_paper_entry_id: '2500.9999',
        },
      ])
      .execute();
    await db
      .insertInto('paper_reference')
      .values([
        {
          belonging_paper_entry_id: '1000.0002',
          referenced_paper_entry_id: '1000.0001',
        },
        {
          belonging_paper_entry_id: '1000.0003',
          referenced_paper_entry_id: '1000.0001',
        },
        {
          belonging_paper_entry_id: '1000.0003',
          referenced_paper_entry_id: '0700.1234',
        },
        // 0002 and 0003 share two references (0001 and 0700.1234), 0004 one
        {
          belonging_paper_entry_id: '1000.0002',
          referenced_paper_entry_id: '0700.1234',
        },
        {
          belonging_paper_entry_id: '1000.0002',
          referenced_paper_entry_id: '1000.0004',
        },
        {
          belonging_paper_entry_id: '1000.0004',
          referenced_paper_entry_id: '0700.1234',
        },
      ])
      .execute();
  });

  afterAll(async () => {
    await app.close();
  });

  const get = async (url: string) => {
    const res = await request(app.getHttpServer()).get(url).expect(200);
    return res.body as Page;
  };
  const ids = (page: Page) => page.items.map((p) => p.entry_id);

  it('sorts by citations on arXiv plus the ones elsewhere', async () => {
    const page = await get('/papers?sort=citations');
    expect(ids(page)).toEqual([
      '1000.0002',
      '1000.0001',
      '1000.0003',
      '1000.0004',
    ]);
    expect(page.total).toBe(4);
  });

  it('matches a category anywhere in the category list', async () => {
    const page = await get('/papers?categories=cs.LG&sort=published');
    expect(ids(page)).toEqual(['1000.0003', '1000.0002', '1000.0001']);
  });

  it('searches title, authors and abstract and takes % literally', async () => {
    expect(ids(await get('/papers?search=hopper'))).toEqual(['1000.0003']);
    expect(ids(await get('/papers?search=100%25'))).toEqual(['1000.0004']);
    expect((await get('/papers?search=%25')).total).toBe(1);
  });

  it('finds words in any order and across title and authors', async () => {
    expect(ids(await get('/papers?search=lovelace%20deep'))).toEqual([
      '1000.0001',
    ]);
    expect(ids(await get('/papers?search=networks%20optimisers'))).toEqual([
      '1000.0001',
    ]);
  });

  it('takes a short word only as a whole word', async () => {
    // "ada" is the author Ada Lovelace, not part of another word
    expect((await get('/papers?search=ada')).total).toBe(3);
    expect((await get('/papers?search=ad')).total).toBe(0);
  });

  it('finds a paper by its arXiv id, with prefix and version', async () => {
    expect(ids(await get('/papers?search=arXiv:1000.0004v2'))).toEqual([
      '1000.0004',
    ]);
  });

  it('puts matches in title or authors before matches in the abstract', async () => {
    // 0002 is cited more, but only its abstract mentions training
    const page = await get('/papers?search=training&sort=relevance');
    expect(ids(page)).toEqual(['1000.0003', '1000.0002']);
    expect(ids(await get('/papers?search=training&sort=citations'))).toEqual([
      '1000.0002',
      '1000.0003',
    ]);
  });

  it('offers similar titles when nothing matches', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers?search=optimizers%20for%20deep%20netwrks&sort=relevance')
      .expect(200);
    const page = res.body as Page & { fuzzy: boolean };
    expect(page.fuzzy).toBe(true);
    expect(ids(page)[0]).toBe('1000.0001');
  });

  it('leaves the abstract and the citation lists out of the map fields', async () => {
    const [first] = (await get('/papers?fields=map&take=1')).items;
    expect(first).toHaveProperty('tsne');
    expect(first).not.toHaveProperty('abstract');
    expect(first).not.toHaveProperty('citations');
  });

  it('skips the count on request and counts on its own route', async () => {
    const page = await get('/papers?search=optimisers&count=none');
    expect(page.total).toBeNull();
    expect(page.items).toHaveLength(2);
    const res = await request(app.getHttpServer())
      .get('/papers/count?search=optimisers')
      .expect(200);
    expect(res.body).toEqual({ total: 2 });
  });

  it('rejects a page size above the limit', async () => {
    await request(app.getHttpServer()).get('/papers?take=20001').expect(400);
  });

  it('returns a single paper with its citation lists, 404 when unknown', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers/1000.0001')
      .expect(200);
    expect(res.body).toMatchObject({
      entry_id: '1000.0001',
      abstract: 'Abstract of Optimisers for deep networks',
    });
    await request(app.getHttpServer()).get('/papers/9999.0000').expect(404);
  });

  it('lists the nearest papers on the map for a paper without an embedding', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers/1000.0001/similar?take=2')
      .expect(200);
    const body = res.body as { basis: string; items: PaperRow[] };
    expect(body.basis).toBe('map');
    expect(body.items).toHaveLength(2);
    expect(body.items.map((p) => p.entry_id)).not.toContain('1000.0001');
    expect(body.items[0]).toHaveProperty('distance', 0);
  });

  it('has no similar papers for an unknown paper', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers/9999.0000/similar')
      .expect(200);
    expect(res.body).toEqual({ basis: null, items: [] });
  });

  it('knows the first and last year of the dataset', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers/years')
      .expect(200);
    expect(res.body).toEqual({ first: 2010, last: 2019 });
  });

  it('limits a list to a range of years', async () => {
    const page = await get(
      '/papers?sort=citations&dateFrom=2015-01-01&dateTo=2018-12-31T23:59:59.999Z',
    );
    expect(ids(page)).toEqual(['1000.0002', '1000.0001']);
  });

  it('counts the papers per category, cross listed and primary', async () => {
    const res = await request(app.getHttpServer())
      .get('/categories')
      .expect(200);
    expect(res.body).toEqual([
      { id: 'cs.LG', papers: 3, primary: 2 },
      { id: 'hep-th', papers: 1, primary: 1 },
      { id: 'stat.ML', papers: 1, primary: 1 },
    ]);
  });

  it('finds citing papers in both edge tables, most cited first', async () => {
    const page = await get('/paper-citations/paper/1000.0001');
    expect(ids(page)).toEqual(['1000.0002', '1000.0003']);
    expect(page.total).toBe(2);
    expect(page.items[0]).not.toHaveProperty('abstract');
    expect(page.items[0]).not.toHaveProperty('total');
  });

  it('finds papers sharing references, at least two of them', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers/1000.0003/connected?by=references')
      .expect(200);
    const body = res.body as {
      by: string;
      items: (PaperRow & { shared: number; score: number })[];
    };
    expect(body.by).toBe('references');
    // 0004 shares only one reference and is left out
    expect(body.items.map((p) => p.entry_id)).toEqual(['1000.0002']);
    expect(body.items[0].shared).toBe(2);
    // 2 shared / sqrt(2 references * 3 references)
    expect(body.items[0].score).toBeCloseTo(2 / Math.sqrt(6));
  });

  it('finds papers cited together', async () => {
    const res = await request(app.getHttpServer())
      .get('/papers/1000.0001/connected?by=citations')
      .expect(200);
    const body = res.body as { items: PaperRow[] };
    // 0001 is cited by 0002 and 0003, both also cite 0700.1234, which is not in the database
    expect(body.items).toEqual([]);
    await request(app.getHttpServer())
      .get('/papers/1000.0001/connected?by=nonsense')
      .expect(400);
  });

  it('keeps the total when the list is cut', async () => {
    const page = await get('/paper-citations/paper/1000.0001?take=1');
    expect(ids(page)).toEqual(['1000.0002']);
    expect(page.total).toBe(2);
  });

  it('finds referenced papers in both edge tables', async () => {
    // known from both tables, listed once
    expect(ids(await get('/paper-references/paper/1000.0003'))).toEqual([
      '1000.0001',
    ]);
    // known from the reference table alone, the more cited one first
    expect(ids(await get('/paper-references/paper/1000.0002'))).toEqual([
      '1000.0001',
      '1000.0004',
    ]);
    expect(await get('/paper-references/paper/1000.0004')).toEqual({
      total: 0,
      items: [],
    });
  });
});
