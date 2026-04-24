from datetime import datetime, timezone
from psycopg import Connection, connect
from psycopg.types.json import Jsonb
from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: Connection | None = None

    def connect(self) -> None:
        if self._connection is not None and not self._connection.closed:
            return

        connection_string = (
            f"host={self._settings.db_host} "
            f"port={self._settings.db_port} "
            f"dbname={self._settings.db_name} "
            f"user={self._settings.db_user} "
            f"password={self._settings.db_password}"
        )

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


# TODO: Consider if this helper function should be moved to a separate utils module

