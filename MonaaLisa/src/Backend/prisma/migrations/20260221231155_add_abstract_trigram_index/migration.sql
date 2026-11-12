-- CreateIndex
CREATE INDEX "paper_abstract_idx" ON "paper" USING GIN ("abstract" gin_trgm_ops);
