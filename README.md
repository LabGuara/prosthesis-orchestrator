# prosthesis Orchestrator

Validates the commands, command feedback and sensor data exchanged over MQTT between the app
and the prosthesis, stores them in PostgreSQL and republishes the validated messages.
See [Data model](#data-model) for what is stored.

## Tech stack
- Python 3.12
- MQTT client: `paho-mqtt`
- Relational database: PostgreSQL 16 (`jsonb` payload)
- Local broker: Eclipse Mosquitto
- Runtime/orchestration: Docker Compose

## Local run

1. Create `.env` from example:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Start all services:

```bash
docker compose up --build
```

3. Start a run with a test feedback, then publish a test sensor batch (readings are only stored
   while a run is in progress):

```bash
docker compose exec mosquitto mosquitto_pub -h localhost -t prosthesis/actions/feedback -m '{"timestamp":"2026-08-17T12:00:04+00:00","command_id":null,"origin":"remote","run_id":"3f2b8c1e-5a4d-4c7e-9b1a-2d6f0e8c4a17","command":"power_on","status":"success","state":"on","gait":1,"current":3000,"message":"test"}'
docker compose exec mosquitto mosquitto_pub -h localhost -t prosthesis/logs -m '{"timestamp":"2026-08-17T12:00:05+00:00","data":[{"t":0.0125,"pJ":3.4}]}'
```

4. Query the stored samples in PostgreSQL:

```bash
docker compose exec postgres psql -U prosthesis_user -d prosthesis_logger -c "SELECT run_id, t_ms, received_at, sensor_data FROM sensor_samples ORDER BY received_at DESC LIMIT 10;"
```

## AWS run

Use `docker-compose.aws.yml` when you deploy to AWS and want only the Python app + PostgreSQL.
This file keeps MQTT settings from `.env` and removes the local Mosquitto service.

```bash
docker compose -f docker-compose.aws.yml up --build -d
```

The app will read these MQTT values from `.env` as usual:

- `MQTT_HOST`
- `MQTT_PORT`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`
- `MQTT_TLS`

For AWS, the app connects to the external broker defined in `.env`, while PostgreSQL stays inside the same Compose stack.

## Migrations

`db/init.sql` runs only when PostgreSQL data volume is created for the first time.
For schema changes after that, run SQL files from `db/migrations` manually.

Run all pending migrations:

```bash
python -m app.migrate
```

docker compose exec postgres psql -U prosthesis_user -d prosthesis_logger -c "SELECT filename, applied_at FROM schema_migrations ORDER BY applied_at DESC;"

## Configuration
All config is done with environment variables in `.env`.

- `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`
- `MQTT_LOGS_TOPIC` (comma-separated)
- `MQTT_QOS`
- `MQTT_POWER_FEEDBACK_TOPIC`, `MQTT_POWER_FEEDBACK_VALIDATED_TOPIC`
- `MQTT_COLLECTIONS_TOPIC`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `LOG_LEVEL`

## Commands

Every command has the same shape, whatever its type. The app publishes it on
`MQTT_COMMAND_LOGS_TOPIC` (default `prosthesis/actions`):

```json
{"timestamp": "2026-08-17T12:00:00.000Z", "command_type": 2, "value": 1, "collection_id": "8c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f"}
```

The command is identified by `command_type` alone; `value` is validated against the range of
that type:

| `command_type` | Command | `value` |
| --- | --- | --- |
| `1` | gait mode | `1`-`9` |
| `2` | power | `1` on, `2` off |
| `3` | actuator current | `3000`-`15000` (mA) |

`collection_id` is the data collection the app had open when it sent the command, or `null` (see
[Data collections](#data-collections)).

Each valid command is stored in `command_logs` (`timestamp` becomes `issued_at`, the time the
orchestrator got it becomes `received_at`) and republished on `MQTT_COMMAND_LOGS_VALIDATED_TOPIC`
(default `prosthesis/actions/validated`) with the id it was stored under, which the bridge echoes
in its feedback. The `collection_id` is not stored with the command, only passed on:

```json
{"command_id": 42, "timestamp": "2026-08-17T12:00:00+00:00", "command_type": 2, "value": 1, "collection_id": "8c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f"}
```

Malformed commands (missing field, unknown type or value out of range) are logged and discarded.
A malformed `collection_id` only loses the collection, with a warning: the command still goes
through, since a stop must never be discarded over it.

## Command feedback

The communication bridge answers every command, and reports every stop it carries out on its
own, with a JSON message on `MQTT_POWER_FEEDBACK_TOPIC` (default `prosthesis/actions/feedback`).
The value must match the bridge's own `MQTT_POWER_FEEDBACK_TOPIC` on the Raspberry Pi.

```json
{
  "timestamp": "2026-08-17T12:00:04+00:00",
  "command_id": 42,
  "origin": "remote",
  "run_id": "3f2b8c1e-5a4d-4c7e-9b1a-2d6f0e8c4a17",
  "collection_id": "8c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f",
  "command": "power_on",
  "status": "success",
  "state": "on",
  "gait": 1,
  "current": 3000,
  "message": "started RoboticLegControl with gait 1 and current 3000 (sudo pid 4312)"
}
```

`origin` is `remote` for the answer to a command and `internal` when the prosthesis acted on its
own (a stop requested on the Pi), in which case `command_id` is `null`. `gait` and `current` are
the settings the prosthesis runs with, so they are `null` while it is off. `run_id` is the run
the feedback belongs to (see [Runs](#runs)), and `collection_id` the data collection of that run,
or `null` (see [Data collections](#data-collections)).

For each feedback message the orchestrator, in one transaction:

1. stores it in `command_feedback_logs` (`timestamp` becomes `issued_at`); a `command_id` this
   database does not know is stored as `null`, with a warning;
2. updates `runs` (see [Runs](#runs));

and then republishes it on `MQTT_POWER_FEEDBACK_VALIDATED_TOPIC` (default
`prosthesis/actions/feedback/validated`).

Malformed feedback (missing field, unknown enum value, `gait`/`current` missing while on) is
logged and discarded.

## Runs

A run is one start of the control program that passed its startup check: every command that
leaves the prosthesis running on a new program (power on, new gait, new current) starts one. The
bridge names it with a UUID v4 and sends it as `run_id` on the feedback that started it and on the
feedback that ended it. For each feedback the orchestrator:

- **prosthesis on, unknown `run_id`**: the reported run started. The run in progress, if any,
  ends with this feedback (a gait or current change ends one run and starts the next with a
  single feedback), and the new run is created with `started_by_feedback_id` = this feedback, in
  the data collection the feedback names;
- **prosthesis on, known `run_id`**: the run kept going (e.g. a power on while already on);
  nothing changes;
- **prosthesis off**: the run in progress ends with this feedback (`ended_by_feedback_id`).

At most one run is in progress at a time (a partial unique index enforces it).

## Data collections

A data collection is a session in which the app groups the runs of one volunteer. When the
collection starts, the app names it with a UUID v4 and announces it on `MQTT_COLLECTIONS_TOPIC`
(default `prosthesis/collections`):

```json
{"collection_id": "8c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f", "volunteer": "Maria Souza"}
```

The orchestrator stores it in `collections`. `volunteer` is the name typed in the app, which is not
unique: the same volunteer can come back for another collection. A malformed announcement
(missing field, `collection_id` not a UUID, empty `volunteer`) is logged and discarded.

The app then sends the `collection_id` with every command it issues while the collection is open;
the bridge keeps the collection of the command that started a run and reports it on every
feedback of that run, and the orchestrator links the run to it (`runs.collection_id`). A run
started outside a collection has `collection_id` `null`. If a run reaches the orchestrator before
the announcement of its collection, the collection is created without a volunteer (`null`), which
the announcement fills in if it arrives later.

A collection starts and ends with its first and last runs (`ended_at` is that of the last run that
ended):

```sql
SELECT min(started.issued_at) AS started_at, max(ended.issued_at) AS ended_at
FROM runs
JOIN command_feedback_logs started ON started.id = runs.started_by_feedback_id
LEFT JOIN command_feedback_logs ended ON ended.id = runs.ended_by_feedback_id
WHERE runs.collection_id = '8c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f';
```

## Sensor data

The bridge forwards each batch of readings from the control program on `MQTT_LOGS_TOPIC`
(default `prosthesis/logs`):

```json
{
  "timestamp": "2026-08-17T12:00:05.012345+00:00",
  "data": [{"s": 1, "t": 2.0125, "pJ": 3.4, "cJ": 512, "cJl": 512, "pP": 0.1, "cP": 80, "cPl": 80, "g1": 41.2, "g2": 30.5, "g3": 12.8, "g4": 0.4}]
}
```

Besides the clock, each reading has the microstate (`s`), the angle, current and limited current
of the knee (`pJ`, `cJ`, `cJl`) and of the ankle (`pP`, `cP`, `cPl`), and the four ground
reaction force sensors (`g1` to `g4`, which have no unit).

The bridge only forwards readings while a run is in progress, and publishes a run's feedback
before its first reading, so every batch is stored under the run in progress when it arrives.
Each reading becomes one row of `sensor_samples`: `t` (the prosthesis clock, in seconds since
the start of the run) is stored as whole milliseconds in `t_ms`, the other channels go to
`sensor_data`. A redelivered batch is skipped sample by sample (`(run_id, t_ms)` is the primary
key). Batches that arrive with no run in progress are not stored (a warning is logged once).
The readings are republished on `MQTT_LOGS_VALIDATED_TOPIC` (default `prosthesis/logs/validated`) as
`{"run_id": "...", "value": [ ... ]}`, with `run_id` `null` when they were not stored.

## Data model

| Table | One row per |
| --- | --- |
| `command_logs` | command received from the app |
| `command_feedback_logs` | feedback from the bridge, linked to its command (`command_id`) |
| `runs` | run of the control program (`id` is the UUID from the bridge), with the feedback that started (`started_by_feedback_id`) and ended (`ended_by_feedback_id`) it, and the data collection it belongs to (`collection_id`); the end is `null` while it is in progress, the collection outside one |
| `collections` | data collection, with its `id` (the UUID from the app) and `volunteer` (the name typed in the app, not unique; `null` until the collection's announcement arrives) |
| `sensor_samples` | reading, keyed by `(run_id, t_ms)` |

The gait mode of a feedback is stored as `gait_mode_enum` (`WALKING` to `STAND_TO_SIT`, modes `1`-`9`
of the MQTT messages, in that order).

Migrations `20261018_007` to `20261018_019` create this model, one enum or table per migration,
keep the existing rows of `command_logs` and drop the old `logs` table and `log_level` enum.
Migrations `20261031_020` to `20261031_022` add `collections`, `runs.collection_id` and
`collections.volunteer`; the runs stored before them stay outside any collection.

## Cloud migration (same app image)
For production/cloud, keep this Python app unchanged and switch only endpoints/credentials:

1. Broker options (managed MQTT):
   - HiveMQ Cloud
   - EMQX Cloud
2. Database options (managed PostgreSQL):
   - Neon
   - Supabase
   - Railway

Then set cloud values in environment variables (including auth/TLS settings if needed).

## Notes
- This MVP is designed for readability and easy setup.
- Works on different OS and CPU architectures through Docker images.
- For higher throughput in the future, add batching/queueing before DB insert.
