from datetime import datetime, timezone
import logging
from pathlib import Path
from psycopg import Connection, connect
from psycopg.types.json import Jsonb
from app.config import Settings, load_settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: Connection | None = None

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

    def insert_log(self, message_id: str, payload: dict) -> None:
        if self._connection is None or self._connection.closed:
            self.connect()

        # TODO: Consider sending a timestamp from the device instead of using the server time
        received_at = datetime.now(timezone.utc)

        query = """
            INSERT INTO message_logs (id, received_at, payload)
            VALUES (%s, %s, %s)
        """

        assert self._connection is not None
        with self._connection.cursor() as cursor:
            cursor.execute(query, (message_id, received_at, Jsonb(payload)))
        self._connection.commit()

    def insert_command_log(
        self,
        message_id: str,
        command_type: int,
        value: float
    ) -> None:
        if self._connection is None or self._connection.closed:
            self.connect()

        received_at = datetime.now(timezone.utc)
        query = """
            INSERT INTO command_logs (id, received_at, command_type, value)
            VALUES (%s, %s, %s, %s)
        """

        assert self._connection is not None
        with self._connection.cursor() as cursor:
            cursor.execute(query, (message_id, received_at, command_type, value))
        self._connection.commit()

    """" Migration management methods """

    def _ensure_migrations_table(self) -> None:
        assert self._connection is not None

        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

        self._connection.commit()

    def _get_applied(self) -> set[str]:
        assert self._connection is not None

        with self._connection.cursor() as cursor:
            cursor.execute("SELECT filename FROM schema_migrations")
            return {row[0] for row in cursor.fetchall()}

    def _pending_files(self) -> list[Path]:
        migrations_dir = Path(__file__).resolve().parent.parent / "db" / "migrations"
        return sorted(migrations_dir.glob("*.sql"))

    def run_migrations(self) -> None:
        assert self._connection is not None

        self._ensure_migrations_table()
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
