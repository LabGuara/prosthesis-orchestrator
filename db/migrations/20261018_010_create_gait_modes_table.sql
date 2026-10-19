BEGIN;

CREATE TABLE gait_modes (
    id SMALLINT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO gait_modes (id, name) VALUES
    (1, 'WALKING'),
    (2, 'STAIR_ASCENT'),
    (3, 'STANDING'),
    (4, 'STAIR_DESCENT'),
    (5, 'UPSLOPE_WALKING'),
    (6, 'DOWNSLOPE_WALKING'),
    (7, 'SITTING'),
    (8, 'SIT_TO_STAND'),
    (9, 'STAND_TO_SIT');

COMMIT;
