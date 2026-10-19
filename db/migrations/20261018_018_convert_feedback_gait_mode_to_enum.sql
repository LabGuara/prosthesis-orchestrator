BEGIN;

ALTER TABLE command_feedback_logs ADD COLUMN gait_mode gait_mode_enum;

UPDATE command_feedback_logs f
SET gait_mode = g.name::gait_mode_enum
FROM gait_modes g
WHERE g.id = f.gait_mode_id;

ALTER TABLE command_feedback_logs DROP CONSTRAINT command_feedback_logs_settings_only_when_on;

ALTER TABLE command_feedback_logs DROP COLUMN gait_mode_id;

ALTER TABLE command_feedback_logs ADD CONSTRAINT command_feedback_logs_settings_only_when_on CHECK (
    (power_state = 'ON' AND gait_mode IS NOT NULL AND current_limit IS NOT NULL)
    OR (power_state = 'OFF' AND gait_mode IS NULL AND current_limit IS NULL)
);

COMMIT;
