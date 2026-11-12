-- migrate:up
-- Schema as it was after the last Prisma migration (2026-02-21), without the
-- legacy tables and unused indexes that later migrations remove anyway.
-- Everything uses IF NOT EXISTS: on a database created by the old Prisma
-- migrations this changes nothing, on an empty database it creates the schema.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- One arXiv paper. tsne holds the UMAP map position {"x", "y", "method"}.
CREATE TABLE IF NOT EXISTS paper (
    id SERIAL PRIMARY KEY,
    entry_id TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT,
    abstract TEXT,
    categories TEXT,
    published TIMESTAMP(3),
    updated TIMESTAMP(3),
    doi TEXT,
    journal_ref TEXT,
    license TEXT,
    url TEXT,
    s2_id TEXT,
    non_arxiv_citation_count INTEGER,
    non_arxiv_reference_count INTEGER,
    related_arxiv_ids JSONB,
    tsne JSONB
);

-- 128-d PCA reduced SPECTER v2 embedding of a paper
CREATE TABLE IF NOT EXISTS embedding (
    id SERIAL PRIMARY KEY,
    belonging_paper_entry_id TEXT NOT NULL,
    content vector(128) NOT NULL
);

-- cited_paper_entry_id is a paper that CITES belonging_paper_entry_id.
-- The other paper does not have to be in the database, so there is no foreign key.
CREATE TABLE IF NOT EXISTS paper_citation (
    belonging_paper_entry_id TEXT NOT NULL,
    cited_paper_entry_id TEXT NOT NULL,
    PRIMARY KEY (belonging_paper_entry_id, cited_paper_entry_id)
);

-- belonging_paper_entry_id references referenced_paper_entry_id
CREATE TABLE IF NOT EXISTS paper_reference (
    belonging_paper_entry_id TEXT NOT NULL,
    referenced_paper_entry_id TEXT NOT NULL,
    PRIMARY KEY (belonging_paper_entry_id, referenced_paper_entry_id)
);

-- Papers Semantic Scholar has no embedding for yet, retried later
CREATE TABLE IF NOT EXISTS uncaught_paper (
    id SERIAL PRIMARY KEY,
    entry_id TEXT NOT NULL,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    categories TEXT,
    published TIMESTAMP(3),
    url TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 4,
    last_checked TIMESTAMP(3),
    created_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS paper_entry_id_key ON paper (entry_id);
CREATE UNIQUE INDEX IF NOT EXISTS paper_s2_id_key ON paper (s2_id);
CREATE INDEX IF NOT EXISTS paper_published_idx ON paper (published DESC);
-- trigram indexes for the ILIKE searches and the category filter
CREATE INDEX IF NOT EXISTS paper_categories_idx ON paper USING gin (categories gin_trgm_ops);
CREATE INDEX IF NOT EXISTS paper_title_idx ON paper USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS paper_authors_idx ON paper USING gin (authors gin_trgm_ops);
CREATE INDEX IF NOT EXISTS paper_abstract_idx ON paper USING gin (abstract gin_trgm_ops);

CREATE UNIQUE INDEX IF NOT EXISTS embedding_belonging_paper_entry_id_key ON embedding (belonging_paper_entry_id);
CREATE INDEX IF NOT EXISTS paper_citation_cited_paper_entry_id_idx ON paper_citation (cited_paper_entry_id);
CREATE INDEX IF NOT EXISTS paper_reference_referenced_paper_entry_id_idx ON paper_reference (referenced_paper_entry_id);
CREATE UNIQUE INDEX IF NOT EXISTS uncaught_paper_entry_id_key ON uncaught_paper (entry_id);

-- migrate:down
-- The baseline is not rolled back, drop the database instead.
