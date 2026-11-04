-- migrate:up
-- Stub papers were placeholder rows created for cited papers that were not
-- fetched yet. Edges no longer need a row for the other paper, so the
-- placeholders are removed. Their citation/reference edges are kept.
-- A stub that was later filled in has a real title and is not touched.
DELETE FROM embedding
WHERE belonging_paper_entry_id IN (
    SELECT entry_id FROM paper WHERE title = '[STUB] Pending Fetch'
);

DELETE FROM paper
WHERE title = '[STUB] Pending Fetch';

-- migrate:down
