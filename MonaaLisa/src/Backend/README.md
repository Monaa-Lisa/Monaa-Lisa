# Monaa-Lisa Backend

Read-only REST API in front of the paper database, built with NestJS. The
Python pipeline writes the papers, this service only reads them, so the
frontend never talks to Postgres itself. Queries are written with Kysely
(typed query builder), the schema belongs to the SQL migrations in
`/db/migrations`.

Originally written by Nico (2025), ported from Prisma to Kysely in November
2026.

## Endpoints

| Route | Returns |
|---|---|
| `GET /health` | `{ status: "ok" }` when the database answers |
| `GET /papers` | a page of papers: `{ items, total, skip, take }` |
| `GET /papers/count` | `{ total }` for the same filters as `GET /papers` |
| `GET /papers/years` | first and last year of publication in the dataset: `{ first, last }` |
| `GET /papers/:entryId` | one paper with the ids of its citations and references |
| `GET /papers/:entryId/similar` | the papers nearest to a paper: `{ basis, items }` |
| `GET /papers/:entryId/connected` | papers connected through the citation graph: `{ by, items }` |
| `POST /papers/batch` | several papers by id, body `{ entryIds: [...] }` |
| `GET /categories` | papers of the dataset per arXiv category: `[{ id, papers, primary }]`, counted once an hour |
| `GET /paper-citations/paper/:entryId` | the papers citing a paper: `{ total, items }` |
| `GET /paper-references/paper/:entryId` | the papers a paper cites: `{ total, items }` |

Query parameters of `GET /papers`:

- `search` takes an arXiv id (`1706.03762`, `arXiv:1706.03762v5`, a link) or
  words in any order. Every word has to occur in the title, the authors or
  the abstract; words of up to three letters only as whole words
- `title`, `author` and `abstract` work the same way on their own column
- `categories` matches anywhere in the category list (`cs.LG` also finds
  papers cross listed there)
- `dateFrom`, `dateTo` limit the publication date
- `sort`: `published` (default), `published_asc`, `citations` or
  `relevance`. Relevance puts papers with all search words in title or
  authors first, then the ones where a word is only in the abstract, each
  group most cited first. When nothing matches it returns up to ten papers
  with a similar title instead (`fuzzy: true`), which catches typing
  mistakes. Citations
  are the ones from arXiv papers plus the ones Semantic Scholar counts outside
  arXiv
- `skip`, `take` (at most 20000)
- `fields=map` leaves out the abstract and the citation lists, which is what
  the paper map loads
- `count=none` skips counting all matches (`total` is then `null`). Counting
  the matches of a common word takes seconds, the first page does not, so the
  search asks for the list and for `/papers/count` separately

The two citation routes return the most cited papers first, 500 by default
(`take`, at most 2000), and `total` says how many there are. They read both
edge tables in both directions: Semantic Scholar caps the list of citing
papers for popular ones, but every citing paper in the database lists the
paper among its own references.

`/papers/:entryId/similar` returns the nearest papers first, 20 by default
(`take`, at most 40), each with its `distance`. `basis` says what was
compared: `embedding` is the cosine distance of the 128-d embeddings (hnsw
index), `map` the distance on the 2-d map for a paper whose embedding is not
in the database, `null` when the paper has neither.

`/papers/:entryId/connected?by=references` returns the papers that cite the
same papers as this one (bibliographic coupling), `by=citations` the papers
that are cited together with it (co-citation). Every item has `shared` (the
number of common references, or of papers citing both; at least two) and
`score`, which is `shared` divided by the geometric mean of the two list
lengths, so long lists do not win by size alone. 30 items by default (`take`,
at most 100), best score first.

## Running

```
npm ci
DATABASE_URL=postgres://user:password@host:5432/monaa npm run start:dev
```

Other settings: `PORT` (3000), `FRONTEND_ORIGIN` (comma separated origins
allowed by CORS), `TRUST_PROXY` (number of reverse proxies in front).

## Tests

`npm test` runs the unit tests, they need no database.

`npm run test:e2e` starts the whole application. The paper tests in
`test/papers.e2e-spec.ts` need a throwaway Postgres with the migrations
applied. They empty the paper tables and fill in their own rows, so they only
run when the database name ends in `_test` and are skipped otherwise:

```
docker run -d --name monaa-test-db -e POSTGRES_PASSWORD=test -e POSTGRES_DB=monaa_test -p 5433:5432 pgvector/pgvector:pg16
export DATABASE_URL="postgres://postgres:test@localhost:5433/monaa_test?sslmode=disable"
docker run --rm --network host -v "$PWD/../../../db:/db" -e DATABASE_URL ghcr.io/amacneil/dbmate:2 --migrations-dir /db/migrations --no-dump-schema up
npm run test:e2e
```
