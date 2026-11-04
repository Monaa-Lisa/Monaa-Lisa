-- migrate:up
-- Stores how many arXiv papers cite each paper, so sort=citations can use an
-- index instead of counting the whole paper_citation table on every request.

-- this index was never used by any query
DROP INDEX IF EXISTS paper_categories_non_arxiv_citation_count_idx;

ALTER TABLE paper ADD COLUMN IF NOT EXISTS arxiv_citation_count INTEGER NOT NULL DEFAULT 0;

-- fill the column for papers that are already in the database
UPDATE paper p
SET arxiv_citation_count = c.cnt
FROM (
    SELECT belonging_paper_entry_id, COUNT(*)::int AS cnt
    FROM paper_citation
    GROUP BY belonging_paper_entry_id
) c
WHERE c.belonging_paper_entry_id = p.entry_id;

CREATE INDEX IF NOT EXISTS paper_arxiv_citation_count_id_idx ON paper (arxiv_citation_count DESC, id);

-- migrate:down
