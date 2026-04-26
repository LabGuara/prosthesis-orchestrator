BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'log_level') THEN
        CREATE TYPE log_level AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR');
    END IF;
END
$$;

ALTER TABLE IF EXISTS message_logs RENAME TO logs;

DROP INDEX IF EXISTS idx_message_logs_received_at;
DROP INDEX IF EXISTS idx_message_logs_id;

ALTER TABLE logs ADD COLUMN IF NOT EXISTS "timestamp" TIMESTAMPTZ NOT NULL;

ALTER TABLE logs ADD COLUMN IF NOT EXISTS level log_level NOT NULL;

ALTER TABLE logs ADD COLUMN IF NOT EXISTS sensor_name TEXT NOT NULL;

ALTER TABLE logs ADD COLUMN IF NOT EXISTS message TEXT NOT NULL;

ALTER TABLE logs DROP COLUMN IF EXISTS payload;
ALTER TABLE logs DROP COLUMN IF EXISTS received_at;

CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs ("timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_logs_id ON logs (id);

COMMIT;
