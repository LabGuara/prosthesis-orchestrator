import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from psycopg import Connection, Cursor, connect
from psycopg.types.json import Jsonb

from app.settings import Settings
from app.models.command_log import CommandLog
from app.models.command_feedback_log import CommandFeedbackLog, ProsthesisPowerState
from app.models.data_collection import DataCollection
from app.models.sensor_batch import SensorBatch


T = TypeVar("T")


class DatabaseService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: Connection | None = None


    """" Connection management methods """

    def _connection_string(self) -> str:
        return (
            f"host={self._settings.db_host} "
            f"port={self._settings.db_port} "
            f"dbname={self._settings.db_name} "
            f"user={self._settings.db_user} "
            f"password={self._settings.db_password}"
        )

    def connect(self) -> None:
        if self._connection is not None and not self._connection.closed:
            return

        connection_string = self._connection_string()
        self._connection = connect(connection_string)

    def close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()

    def _in_transaction(self, work: Callable[[Cursor], T]) -> T:
        """Runs `work` in one transaction: committed if it returns, rolled back if it raises,
        so a failed statement never leaves the connection stuck in an aborted transaction."""
        if self._connection is None or self._connection.closed:
            self.connect()

        assert self._connection is not None
        try:
            with self._connection.cursor() as cursor:
                result = work(cursor)
            self._connection.commit()
            return result
        except Exception:
            self._connection.rollback()
            raise


    """" Migration management methods """

    def _get_applied(self) -> set[str]:
        assert self._connection is not None

        with self._connection.cursor() as cursor:
            cursor.execute("SELECT filename FROM schema_migrations")
            return {row[0] for row in cursor.fetchall()}

    def _pending_files(self) -> list[Path]:
        migrations_dir = Path(__file__).resolve().parent.parent.parent / "db" / "migrations"
        return sorted(migrations_dir.glob("*.sql"))

    def run_migrations(self) -> None:
        assert self._connection is not None

        applied = self._get_applied()

        for migration_file in self._pending_files():
            if migration_file.name in applied:
                continue

            sql = migration_file.read_bytes()

            with self._connection.cursor() as cursor:
                cursor.execute(sql)
                cursor.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (migration_file.name,),
                )

            self._connection.commit()
            logging.info("Applied migration: %s", migration_file.name)

        logging.info("Migrations are up to date.")


    """ Data manipulation methods """

    def insert_command_log(self, command_log: CommandLog) -> int:
        """Stores the command and returns the id it got, which the feedback will reference."""

        def work(cursor: Cursor) -> int:
            cursor.execute(
                """
                INSERT INTO command_logs (issued_at, received_at, command_type, value)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    command_log.issued_at,
                    command_log.received_at,
                    command_log.command_type.name,
                    command_log.value,
                ),
            )
            row = cursor.fetchone()
            assert row is not None
            return row[0]

        command_log.id = self._in_transaction(work)
        return command_log.id

    def insert_collection(self, collection: DataCollection) -> None:
        """Stores a collection the app started. A run whose feedback arrived first may have
        created it already, without a volunteer; the volunteer is filled in then."""

        def work(cursor: Cursor) -> None:
            cursor.execute(
                """
                INSERT INTO collections (id, volunteer) VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET volunteer = EXCLUDED.volunteer
                """,
                (collection.id, collection.volunteer),
            )

        self._in_transaction(work)

    def insert_command_feedback_log(self, feedback: CommandFeedbackLog) -> int:
        """Stores the feedback and updates the runs it starts or ends, in one transaction."""

        def work(cursor: Cursor) -> int:
            command_id = feedback.command_id
            if command_id is not None:
                cursor.execute("SELECT 1 FROM command_logs WHERE id = %s", (command_id,))
                if cursor.fetchone() is None:
                    logging.warning(
                        "Feedback references unknown command_id=%s; storing it without the link",
                        command_id,
                    )
                    command_id = None

            cursor.execute(
                """
                INSERT INTO command_feedback_logs (
                    command_id, result_status, power_state, gait_mode, current_limit,
                    message, origin, issued_at, received_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    command_id,
                    feedback.result_status.name,
                    feedback.power_state.name,
                    feedback.gait_mode.name if feedback.gait_mode is not None else None,
                    feedback.current_limit,
                    feedback.message,
                    feedback.origin.name,
                    feedback.issued_at,
                    feedback.received_at,
                ),
            )
            row = cursor.fetchone()
            assert row is not None
            feedback_id = row[0]

            self._update_runs(cursor, feedback, feedback_id)
            return feedback_id

        feedback.id = self._in_transaction(work)
        return feedback.id

    def _update_runs(self, cursor: Cursor, feedback: CommandFeedbackLog, feedback_id: int) -> None:
        """Opens and closes runs. A feedback that leaves the prosthesis on with a run id this
        database does not know started that run: the run in progress, if any, ends and the new one
        starts, in the data collection the feedback names (created without a volunteer if the app's
        message starting it has not arrived). A known run id means the run kept going (e.g. a power
        on while already on). A feedback that leaves the prosthesis off ends the run in progress."""

        cursor.execute("SELECT id FROM runs WHERE ended_by_feedback_id IS NULL")
        row = cursor.fetchone()
        in_progress: UUID | None = row[0] if row is not None else None

        if feedback.power_state is ProsthesisPowerState.OFF:
            if in_progress is None:
                return
            if feedback.run_id is not None and feedback.run_id != in_progress:
                logging.warning(
                    "Feedback id=%s ended run %s, but the run in progress here is %s; ending it",
                    feedback_id,
                    feedback.run_id,
                    in_progress,
                )
            self._end_run(cursor, in_progress, feedback_id)
            return

        if feedback.run_id is None:
            logging.warning(
                "Feedback id=%s leaves the prosthesis on but carries no run_id; runs not updated",
                feedback_id,
            )
            return

        cursor.execute("SELECT ended_by_feedback_id FROM runs WHERE id = %s", (feedback.run_id,))
        row = cursor.fetchone()
        if row is not None:
            if row[0] is not None:
                logging.warning(
                    "Feedback id=%s reports run %s, which already ended; runs not updated",
                    feedback_id,
                    feedback.run_id,
                )
            return

        if in_progress is not None:
            self._end_run(cursor, in_progress, feedback_id)

        if feedback.collection_id is not None:
            cursor.execute(
                "INSERT INTO collections (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (feedback.collection_id,),
            )

        cursor.execute(
            "INSERT INTO runs (id, started_by_feedback_id, collection_id) VALUES (%s, %s, %s)",
            (feedback.run_id, feedback_id, feedback.collection_id),
        )
        logging.info(
            "Run %s started by feedback id=%s in collection %s",
            feedback.run_id,
            feedback_id,
            feedback.collection_id,
        )

    def _end_run(self, cursor: Cursor, run_id: UUID, feedback_id: int) -> None:
        cursor.execute(
            "UPDATE runs SET ended_by_feedback_id = %s WHERE id = %s",
            (feedback_id, run_id),
        )
        logging.info("Run %s ended by feedback id=%s", run_id, feedback_id)

    def insert_sensor_batch(self, batch: SensorBatch) -> tuple[UUID | None, int]:
        """Stores every sample of the batch under the run in progress. Samples already stored (a
        redelivered batch) are skipped. Returns the run and the number of new samples; with no run
        in progress nothing is stored and the run is `None`."""

        def work(cursor: Cursor) -> tuple[UUID | None, int]:
            cursor.execute("SELECT id FROM runs WHERE ended_by_feedback_id IS NULL")
            row = cursor.fetchone()
            if row is None:
                return None, 0

            run_id: UUID = row[0]
            inserted = 0
            for sample in batch.samples:
                cursor.execute(
                    """
                    INSERT INTO sensor_samples (run_id, t_ms, received_at, sensor_data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (run_id, t_ms) DO NOTHING
                    """,
                    (run_id, sample.t_ms, batch.received_at, Jsonb(sample.sensor_data)),
                )
                inserted += cursor.rowcount
            return run_id, inserted

        return self._in_transaction(work)
