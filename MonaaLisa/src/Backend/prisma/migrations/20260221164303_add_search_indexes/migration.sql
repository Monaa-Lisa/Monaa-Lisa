CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- DropIndex
DROP INDEX "embedding_content_idx";

-- DropIndex
DROP INDEX "paper_categories_idx";

-- DropIndex
DROP INDEX "paper_relation_target_id_idx";

-- DropIndex
DROP INDEX "uncaught_paper_retry_queue_idx";

-- CreateIndex
CREATE INDEX "paper_categories_idx" ON "paper" USING GIN ("categories" gin_trgm_ops);

-- CreateIndex
CREATE INDEX "paper_title_idx" ON "paper" USING GIN ("title" gin_trgm_ops);

-- CreateIndex
CREATE INDEX "paper_authors_idx" ON "paper" USING GIN ("authors" gin_trgm_ops);
