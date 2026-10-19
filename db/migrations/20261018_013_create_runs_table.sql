BEGIN;

CREATE TABLE runs (
    id UUID PRIMARY KEY,
    started_by_feedback_id BIGINT NOT NULL UNIQUE REFERENCES command_feedback_logs (id),
    ended_by_feedback_id BIGINT UNIQUE REFERENCES command_feedback_logs (id)
);

CREATE UNIQUE INDEX runs_single_in_progress ON runs ((true)) WHERE ended_by_feedback_id IS NULL;

COMMIT;
