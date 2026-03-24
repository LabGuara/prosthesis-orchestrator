BEGIN;

CREATE TABLE IF NOT EXISTS command_logs (
    id TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    command_type INTEGER NOT NULL,
    value NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_command_logs_received_at ON command_logs (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_logs_id ON command_logs (id);

COMMIT;
