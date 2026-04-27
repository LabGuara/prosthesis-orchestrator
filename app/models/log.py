import json
from dataclasses import dataclass
from datetime import datetime

from app.models.log_level import LogLevel
from app.utils import parse_timestamp


@dataclass(init=False)
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
        return json.dumps(
            {
                "level": self.level.name,
                "timestamp": self.timestamp.isoformat(),
                "sensor_name": self.sensor_name,
                "message": self.message,
            }
        )
