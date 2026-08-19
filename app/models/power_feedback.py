from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json

from app.models.log import Log
from app.models.log_level import LogLevel
from app.utils import parse_timestamp


class PowerCommand(StrEnum):
    POWER_ON = "power_on"
    POWER_OFF = "power_off"


class PowerFeedbackStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ProsthesisState(StrEnum):
    ON = "on"
    OFF = "off"


def _parse_enum_field[T: StrEnum](payload: dict, key: str, enum_type: type[T]) -> T:
    value = payload.get(key)

    if not isinstance(value, str):
        raise ValueError(f"Missing or non-string field: {key}")

    try:
        return enum_type(value)
    except ValueError:
        raise ValueError(f"Unsupported value for field {key}: {value!r}") from None


@dataclass(slots=True, init=False)
class PowerFeedback:
    id: str
    timestamp: datetime
    command: PowerCommand
    status: PowerFeedbackStatus
    state: ProsthesisState
    message: str

    def __init__(self, id: str, payload: dict) -> None:
        self.id = id

        if "timestamp" not in payload:
            raise ValueError("Missing field: timestamp")
        self.timestamp = parse_timestamp(payload.get("timestamp"))

        self.command = _parse_enum_field(payload, "command", PowerCommand)
        self.status = _parse_enum_field(payload, "status", PowerFeedbackStatus)
        self.state = _parse_enum_field(payload, "state", ProsthesisState)

        message = payload.get("message")
        if not isinstance(message, str):
            raise ValueError("Missing or non-string field: message")
        self.message = message

    @property
    def level(self) -> LogLevel:
        if self.status is PowerFeedbackStatus.SUCCESS:
            return LogLevel.INFO
        return LogLevel.ERROR

    def build_log(self) -> Log:
        payload = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.name,
            "sensor_name": "power_feedback",
            "message": self.build_log_message(),
        }
        return Log(self.id, payload)

    def build_log_message(self) -> str:
        return (
            f"{self.command.value} {self.status.value} "
            f"(state: {self.state.value}): {self.message}"
        )

    def generate_parsed_log_message(self) -> str:
        parsed_payload = {
            "timestamp": self.timestamp.isoformat(),
            "command": self.command.value,
            "status": self.status.value,
            "state": self.state.value,
            "message": self.message,
        }
        return json.dumps(parsed_payload, ensure_ascii=False)
