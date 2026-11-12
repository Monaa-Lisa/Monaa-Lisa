-- migrate:up
-- Papers saved by the incremental pipeline had their tsne value encoded twice
-- (a JSON string containing the object). Turn those back into real objects.
UPDATE paper
SET tsne = (tsne #>> '{}')::jsonb
WHERE jsonb_typeof(tsne) = 'string';

-- migrate:down
