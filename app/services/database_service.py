import logging
from pathlib import Path
from psycopg import Connection, connect
from app.config import Settings
from app.models.command_log import CommandLog
from app.models.log import Log


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


    """" Migration management methods """

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

    def insert_log(self, log: Log) -> None:
        if self._connection is None or self._connection.closed:
            self.connect()

        query = """
            INSERT INTO logs (id, "timestamp", level, sensor_name, message)
            VALUES (%s, %s, %s, %s, %s)
        """

        assert self._connection is not None
        with self._connection.cursor() as cursor:
            cursor.execute(
                query,
                (log.id, log.timestamp, log.level.name, log.sensor_name, log.message),
            )
        self._connection.commit()

    def insert_command_log(self, command_log: CommandLog) -> None:
        if self._connection is None or self._connection.closed:
            self.connect()

        query = """
            INSERT INTO command_logs (id, "timestamp", command_type, value)
            VALUES (%s, %s, %s, %s)
        """


        command_type_mapping = {
            "GaitMode": "GAIT_MODE"
        }

        command_type = command_type_mapping[command_log.command.__class__.__name__]

        assert self._connection is not None
        with self._connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    command_log.id,
                    command_log.timestamp,
                    command_type,
                    command_log.command.value,
                ),
            )
        self._connection.commit()