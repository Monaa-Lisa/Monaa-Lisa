-- migrate:up
-- Nearest papers on the map (GET /papers/:entryId/similar falls back to them
-- for a paper without an embedding): k nearest neighbour search on the UMAP
-- position.
CREATE INDEX IF NOT EXISTS paper_map_position_idx
    ON paper USING gist (point((tsne->>'x')::float8, (tsne->>'y')::float8))
    WHERE tsne IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS paper_map_position_idx;
