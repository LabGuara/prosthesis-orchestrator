BEGIN;

CREATE TABLE command_feedback_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    command_id BIGINT REFERENCES command_logs (id),
    result_status result_status_enum NOT NULL,
    power_state power_state_enum NOT NULL,
    gait_mode_id SMALLINT REFERENCES gait_modes (id),
    current_limit INTEGER,
    message TEXT NOT NULL,
    origin feedback_origin_enum NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT command_feedback_logs_settings_only_when_on CHECK (
        (power_state = 'ON' AND gait_mode_id IS NOT NULL AND current_limit IS NOT NULL)
        OR (power_state = 'OFF' AND gait_mode_id IS NULL AND current_limit IS NULL)
    ),
    CONSTRAINT command_feedback_logs_internal_has_no_command CHECK (
        origin = 'REMOTE' OR command_id IS NULL
    )
);

CREATE INDEX idx_command_feedback_logs_command_id ON command_feedback_logs (command_id);
CREATE INDEX idx_command_feedback_logs_issued_at ON command_feedback_logs (issued_at DESC);

COMMIT;
