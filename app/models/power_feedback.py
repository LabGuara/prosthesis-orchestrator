from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json

from app.models.command_log import GaitMode
from app.models.log import Log
from app.models.log_level import LogLevel
from app.utils import parse_int_field, parse_timestamp


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


def _parse_gait_field(payload: dict, key: str) -> GaitMode:
    value = parse_int_field(payload, key)

    if value is None:
        raise ValueError(f"Missing or non-integer field: {key}")

    try:
        return GaitMode(value)
    except ValueError:
        raise ValueError(f"Unsupported value for field {key}: {value!r}") from None


def _parse_status_field(payload: dict) -> PowerFeedbackStatus:
    # The bridge sends `success` as a boolean; earlier builds sent `status` as a string.
    if "status" in payload:
        return _parse_enum_field(payload, "status", PowerFeedbackStatus)

    success = payload.get("success")
    if not isinstance(success, bool):
        raise ValueError("Missing or non-boolean field: success")

    return PowerFeedbackStatus.SUCCESS if success else PowerFeedbackStatus.FAILURE


@dataclass(slots=True, init=False)
class PowerFeedback:
    id: str
    timestamp: datetime
    command: PowerCommand
    status: PowerFeedbackStatus
    state: ProsthesisState
    gait: GaitMode
    message: str

    def __init__(self, id: str, payload: dict) -> None:
        self.id = id

        if "timestamp" not in payload:
            raise ValueError("Missing field: timestamp")
        self.timestamp = parse_timestamp(payload.get("timestamp"))

        self.command = _parse_enum_field(payload, "command", PowerCommand)
        self.status = _parse_status_field(payload)
        self.state = _parse_enum_field(payload, "state", ProsthesisState)
        self.gait = _parse_gait_field(payload, "gait")

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
            f"(state: {self.state.value}, gait: {self.gait.name.lower()}): {self.message}"
        )

    def generate_parsed_log_message(self) -> str:
        parsed_payload = {
            "timestamp": self.timestamp.isoformat(),
            "command": self.command.value,
            "status": self.status.value,
            "state": self.state.value,
            "gait": self.gait.value,
            "message": self.message,
        }
        return json.dumps(parsed_payload, ensure_ascii=False)
