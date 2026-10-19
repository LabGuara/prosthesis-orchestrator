BEGIN;

CREATE TABLE sensor_samples (
    run_id UUID NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    t_ms INTEGER NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    sensor_data JSONB NOT NULL,
    PRIMARY KEY (run_id, t_ms)
);

COMMIT;
