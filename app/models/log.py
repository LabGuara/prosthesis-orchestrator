from dataclasses import dataclass
from datetime import datetime
import json

from app.models.log_level import LogLevel
from app.models.parsed_log import ParsedLog
from app.utils import parse_timestamp


@dataclass(slots=True, init=False)
class Log:
    id: str
    timestamp: datetime
    level: LogLevel
    sensor_name: str
    message: str

    def __init__(self, id: str, payload: dict) -> None:
        self.id = id
        self.timestamp = parse_timestamp(payload.get("timestamp"))

        raw_level = str(payload.get("level", "INFO")).upper()
        self.level = LogLevel.__members__.get(raw_level, LogLevel.INFO)
        self.sensor_name = str(payload.get("sensor_name", "unknown"))

        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            message = json.dumps(payload, ensure_ascii=False)
        self.message = message

    def generate_parsed_log_message(self) -> str:
        parsed_log = ParsedLog(
            level=self.level,
            timestamp=self.timestamp,
            sensor_name=self.sensor_name,
            message=self.message,
        )
        return parsed_log.generate_parsed_log_message()
