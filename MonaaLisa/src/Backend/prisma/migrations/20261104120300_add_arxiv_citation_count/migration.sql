-- Stores how many arXiv papers cite each paper, so sort=citations can use an
-- index instead of counting the whole paper_citation table on every request.

-- DropIndex (was never used by any query)
DROP INDEX "paper_categories_non_arxiv_citation_count_idx";

-- AlterTable
ALTER TABLE "paper" ADD COLUMN "arxiv_citation_count" INTEGER NOT NULL DEFAULT 0;

-- Fill the new column for papers that are already in the database
UPDATE "paper" p
SET "arxiv_citation_count" = c.cnt
FROM (
    SELECT "belonging_paper_entry_id", COUNT(*)::int AS cnt
    FROM "paper_citation"
    GROUP BY "belonging_paper_entry_id"
) c
WHERE c."belonging_paper_entry_id" = p."entry_id";

-- CreateIndex
CREATE INDEX "paper_arxiv_citation_count_id_idx" ON "paper"("arxiv_citation_count" DESC, "id");
