BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'command_type_enum') THEN
        CREATE TYPE command_type_enum AS ENUM ('GAIT_MODE');
    END IF;
END
$$;

ALTER TABLE command_logs RENAME COLUMN received_at TO "timestamp";

ALTER TABLE command_logs
    ALTER COLUMN command_type TYPE command_type_enum
    USING 'GAIT_MODE'::command_type_enum;

DROP INDEX IF EXISTS idx_command_logs_received_at;
CREATE INDEX IF NOT EXISTS idx_command_logs_timestamp ON command_logs ("timestamp" DESC);

COMMIT;
