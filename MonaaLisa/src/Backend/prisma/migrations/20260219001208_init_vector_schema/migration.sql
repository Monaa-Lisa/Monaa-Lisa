-- CreateExtension
CREATE EXTENSION IF NOT EXISTS "vector";

-- CreateTable
CREATE TABLE "paper" (
    "id" SERIAL NOT NULL,
    "entry_id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "authors" TEXT,
    "abstract" TEXT,
    "categories" TEXT,
    "published" TIMESTAMP(3),
    "updated" TIMESTAMP(3),
    "doi" TEXT,
    "journal_ref" TEXT,
    "license" TEXT,
    "url" TEXT,
    "s2_id" TEXT,
    "non_arxiv_citation_count" INTEGER,
    "non_arxiv_reference_count" INTEGER,
    "related_arxiv_ids" JSONB,
    "tsne" JSONB,

    CONSTRAINT "paper_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "paper_relation" (
    "source_id" TEXT NOT NULL,
    "target_id" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,

    CONSTRAINT "paper_relation_pkey" PRIMARY KEY ("source_id","target_id")
);

-- CreateTable
CREATE TABLE "reference" (
    "id" SERIAL NOT NULL,
    "belonging_paper_entry_id" TEXT NOT NULL,
    "semanticscholar_obj" JSONB NOT NULL,

    CONSTRAINT "reference_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "citation" (
    "id" SERIAL NOT NULL,
    "belonging_paper_entry_id" TEXT NOT NULL,
    "semanticscholar_obj" JSONB NOT NULL,

    CONSTRAINT "citation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "paper_citation" (
    "belonging_paper_entry_id" TEXT NOT NULL,
    "cited_paper_entry_id" TEXT NOT NULL,

    CONSTRAINT "paper_citation_pkey" PRIMARY KEY ("belonging_paper_entry_id","cited_paper_entry_id")
);

-- CreateTable
CREATE TABLE "paper_reference" (
    "belonging_paper_entry_id" TEXT NOT NULL,
    "referenced_paper_entry_id" TEXT NOT NULL,

    CONSTRAINT "paper_reference_pkey" PRIMARY KEY ("belonging_paper_entry_id","referenced_paper_entry_id")
);

-- CreateTable
CREATE TABLE "embedding" (
    "id" SERIAL NOT NULL,
    "belonging_paper_entry_id" TEXT NOT NULL,
    "content" vector(128) NOT NULL,

    CONSTRAINT "embedding_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "program_run" (
    "id" SERIAL NOT NULL,
    "start_date" TIMESTAMP(3) NOT NULL,
    "is_active" TEXT NOT NULL DEFAULT 'true',

    CONSTRAINT "program_run_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "historical_completion" (
    "id" SERIAL NOT NULL,
    "program_run_id" INTEGER NOT NULL,
    "category" TEXT NOT NULL,
    "start_date" TIMESTAMP(3) NOT NULL,
    "end_date" TIMESTAMP(3),
    "goal_oldest_paper_date" TIMESTAMP(3),
    "goal_reached" TEXT NOT NULL DEFAULT 'false',
    "reached_date" TIMESTAMP(3),
    "oldest_paper_date" TIMESTAMP(3),

    CONSTRAINT "historical_completion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "uncaught_paper" (
    "id" SERIAL NOT NULL,
    "entry_id" TEXT NOT NULL,
    "title" TEXT,
    "authors" TEXT,
    "abstract" TEXT,
    "categories" TEXT,
    "published" TIMESTAMP(3),
    "url" TEXT,
    "retry_count" INTEGER NOT NULL DEFAULT 0,
    "max_retries" INTEGER NOT NULL DEFAULT 4,
    "last_checked" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "uncaught_paper_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "paper_entry_id_key" ON "paper"("entry_id");

-- CreateIndex
CREATE UNIQUE INDEX "paper_s2_id_key" ON "paper"("s2_id");

-- CreateIndex
CREATE INDEX "reference_belonging_paper_entry_id_idx" ON "reference"("belonging_paper_entry_id");

-- CreateIndex
CREATE INDEX "citation_belonging_paper_entry_id_idx" ON "citation"("belonging_paper_entry_id");

-- CreateIndex
CREATE INDEX "paper_citation_cited_paper_entry_id_idx" ON "paper_citation"("cited_paper_entry_id");

-- CreateIndex
CREATE UNIQUE INDEX "embedding_belonging_paper_entry_id_key" ON "embedding"("belonging_paper_entry_id");

-- CreateVectorIndex
CREATE INDEX "embedding_content_idx" ON "embedding" USING hnsw ("content" vector_cosine_ops);

-- CreateIndex
CREATE UNIQUE INDEX "uncaught_paper_entry_id_key" ON "uncaught_paper"("entry_id");

-- Damit findest du schnell alle Relationen, die AUF ein Paper zeigen
CREATE INDEX "paper_relation_target_id_idx" ON "paper_relation" ("target_id");

-- Damit findest du schnell alle Paper, die von einem bestimmten Paper referenziert werden (Reverse-Lookup)
CREATE INDEX "paper_reference_referenced_paper_entry_id_idx" ON "paper_reference" ("referenced_paper_entry_id");

-- Beschleunigt: "ORDER BY published DESC" und "WHERE published > '2023-01-01'"
CREATE INDEX "paper_published_idx" ON "paper" ("published" DESC);

-- Falls du oft nach Kategorien filterst (z.B. "cs.AI")
CREATE INDEX "paper_categories_idx" ON "paper" ("categories");

-- Optimiert die Polling-Loop für fehlende Paper
CREATE INDEX "uncaught_paper_retry_queue_idx" ON "uncaught_paper" ("retry_count", "last_checked");

-- Erlaubt schnelle Suche in Titeln (Postgres TSVector)
-- Achtung: Das verbraucht etwas mehr Speicher!
CREATE INDEX "paper_title_search_idx" ON "paper" USING GIN (to_tsvector('english', title));