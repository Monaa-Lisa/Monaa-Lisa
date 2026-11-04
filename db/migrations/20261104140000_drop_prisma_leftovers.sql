-- migrate:up
-- The schema is managed by these SQL migrations (dbmate) now, not by Prisma.

-- Prisma's own bookkeeping table is not needed any more
DROP TABLE IF EXISTS _prisma_migrations;

-- full text index on the title that no query uses (search uses the trigram indexes)
DROP INDEX IF EXISTS paper_title_search_idx;

-- migrate:down
