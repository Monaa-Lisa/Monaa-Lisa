-- 20260221164303_add_search_indexes dropped these indexes because Prisma did
-- not know about them. They are restored here.

-- Vector index for cosine similarity search on the 128-d embeddings.
-- Building it on a full dataset takes a while.
CREATE INDEX IF NOT EXISTS "embedding_content_idx" ON "embedding" USING hnsw ("content" vector_cosine_ops);

-- Used by the uncaught paper retry job (retry_count < max_retries, last_checked <= cutoff).
-- Now also declared in schema.prisma, so Prisma keeps it.
CREATE INDEX IF NOT EXISTS "uncaught_paper_retry_queue_idx" ON "uncaught_paper" ("retry_count", "last_checked");
