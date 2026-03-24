CREATE TABLE IF NOT EXISTS message_logs (
    id TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_message_logs_received_at ON message_logs (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_message_logs_id ON message_logs (id);
