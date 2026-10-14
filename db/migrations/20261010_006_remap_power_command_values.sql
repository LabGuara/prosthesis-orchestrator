BEGIN;

-- Power commands were 16 (on) and 17 (off), so the bridge could tell them apart from gait
-- modes by value alone. The command type now identifies the command, and power is 1 (on) and
-- 2 (off); older rows are remapped so the column means the same thing for every row.
UPDATE command_logs
SET value = CASE value WHEN 16 THEN 1 WHEN 17 THEN 2 END
WHERE command_type = 'POWER' AND value IN (16, 17);

COMMIT;
