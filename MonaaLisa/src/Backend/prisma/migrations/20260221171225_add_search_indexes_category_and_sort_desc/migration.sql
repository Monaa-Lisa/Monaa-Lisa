-- CreateIndex
CREATE INDEX "paper_categories_non_arxiv_citation_count_idx" ON "paper"("categories", "non_arxiv_citation_count" DESC);
