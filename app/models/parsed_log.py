import json
from datetime import datetime

from app.models.log_level import LogLevel


class ParsedLog:
    def __init__(self, level: LogLevel, timestamp: datetime, sensor_name: str, message: str) -> None:
        self.level = level
        self.timestamp = timestamp
        self.sensor_name = sensor_name
        self.message = message

    def generate_parsed_log_message(self) -> str:
        return self.message