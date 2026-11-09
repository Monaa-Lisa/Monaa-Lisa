-- migrate:up
-- sort=citations orders by all known citations: the ones from arXiv papers
-- (arxiv_citation_count, the list from Semantic Scholar is capped for very
-- popular papers) plus the ones counted outside arXiv. The index on the arXiv
-- count alone is replaced by one on the sum.
DROP INDEX IF EXISTS paper_arxiv_citation_count_id_idx;
CREATE INDEX IF NOT EXISTS paper_total_citation_count_id_idx
    ON paper ((arxiv_citation_count + COALESCE(non_arxiv_citation_count, 0)) DESC, id);

-- migrate:down
DROP INDEX IF EXISTS paper_total_citation_count_id_idx;
CREATE INDEX IF NOT EXISTS paper_arxiv_citation_count_id_idx ON paper (arxiv_citation_count DESC, id);
