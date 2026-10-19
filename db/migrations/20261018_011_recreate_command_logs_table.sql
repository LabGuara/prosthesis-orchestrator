BEGIN;

CREATE TABLE command_logs_new (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    issued_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    command_type command_type_enum NOT NULL,
    value NUMERIC NOT NULL
);

INSERT INTO command_logs_new (issued_at, received_at, command_type, value)
SELECT "timestamp", "timestamp", command_type, value
FROM command_logs
ORDER BY "timestamp";

DROP TABLE command_logs;

ALTER TABLE command_logs_new RENAME TO command_logs;
ALTER SEQUENCE command_logs_new_id_seq RENAME TO command_logs_id_seq;
ALTER INDEX command_logs_new_pkey RENAME TO command_logs_pkey;

CREATE INDEX idx_command_logs_issued_at ON command_logs (issued_at DESC);

COMMIT;
