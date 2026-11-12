-- migrate:up
-- These tables belong to the old per-category scheduler and the earlier
-- Semantic Scholar integration. No code reads or writes them any more.
-- To be safe, the migration stops if one of them still holds data, so nothing
-- is lost by accident. Export or empty the table first if that happens.
DO $$
DECLARE
    t text;
    has_rows boolean;
BEGIN
    FOREACH t IN ARRAY ARRAY['citation', 'reference', 'paper_relation', 'program_run', 'historical_completion'] LOOP
        IF to_regclass(format('public.%I', t)) IS NOT NULL THEN
            EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I)', t) INTO has_rows;
            IF has_rows THEN
                RAISE EXCEPTION 'Table % is not empty, refusing to drop it', t;
            END IF;
        END IF;
    END LOOP;
END $$;

DROP TABLE IF EXISTS citation;
DROP TABLE IF EXISTS reference;
DROP TABLE IF EXISTS paper_relation;
DROP TABLE IF EXISTS historical_completion;
DROP TABLE IF EXISTS program_run;

-- migrate:down
