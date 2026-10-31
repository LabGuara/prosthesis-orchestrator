BEGIN;

ALTER TABLE collections RENAME TO collects;
ALTER TABLE collects RENAME CONSTRAINT collections_pkey TO collects_pkey;

ALTER TABLE runs RENAME COLUMN collection_id TO collect_id;
ALTER TABLE runs RENAME CONSTRAINT runs_collection_id_fkey TO runs_collect_id_fkey;

COMMIT;
