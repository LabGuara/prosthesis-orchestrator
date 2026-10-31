BEGIN;

ALTER TABLE runs ADD COLUMN collection_id UUID REFERENCES collections (id);

COMMIT;
