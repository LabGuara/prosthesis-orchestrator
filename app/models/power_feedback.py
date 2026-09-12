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
    SET_GAIT = "set_gait"
    SET_ACTUATOR_CURRENT = "set_actuator_current"


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


def _parse_optional_current_field(payload: dict, key: str) -> int | None:
    # Reported, not commanded: no range check here, so a surprising value still reaches the log.
    if key not in payload:
        return None

    value = parse_int_field(payload, key)
    if value is None:
        raise ValueError(f"Non-integer field: {key}")

    return value


def _parse_status_field(payload: dict) -> PowerFeedbackStatus:
    # The bridge sends `status` as a string; the boolean `success` is a fallback for older builds.
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
    current: int | None
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
        self.current = _parse_optional_current_field(payload, "current")

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
        details = f"state: {self.state.value}, gait: {self.gait.name.lower()}"
        if self.current is not None:
            details = f"{details}, current: {self.current}"

        return f"{self.command.value} {self.status.value} ({details}): {self.message}"

    def generate_parsed_log_message(self) -> str:
        parsed_payload = {
            "timestamp": self.timestamp.isoformat(),
            "command": self.command.value,
            "status": self.status.value,
            "state": self.state.value,
            "gait": self.gait.value,
            "current": self.current,
            "message": self.message,
        }
        return json.dumps(parsed_payload, ensure_ascii=False)
