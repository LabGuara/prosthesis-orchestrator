from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
from uuid import UUID

from app.models.command_log import GaitMode
from app.utils import parse_int_field, parse_timestamp


class FeedbackCommand(StrEnum):
    """What the bridge did. Not persisted: for a remote feedback it follows from the command."""

    POWER_ON = "power_on"
    POWER_OFF = "power_off"
    SET_GAIT = "set_gait"
    SET_ACTUATOR_CURRENT = "set_actuator_current"


class ResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ProsthesisPowerState(StrEnum):
    ON = "on"
    OFF = "off"


class FeedbackOrigin(StrEnum):
    # Answers a command that came from the app.
    REMOTE = "remote"
    # The prosthesis acted on its own, e.g. a stop requested on the Raspberry Pi.
    INTERNAL = "internal"


def _parse_enum_field[T: StrEnum](payload: dict, key: str, enum_type: type[T]) -> T:
    value = payload.get(key)

    if not isinstance(value, str):
        raise ValueError(f"Missing or non-string field: {key}")

    try:
        return enum_type(value)
    except ValueError:
        raise ValueError(f"Unsupported value for field {key}: {value!r}") from None


def _parse_origin(payload: dict) -> FeedbackOrigin:
    # Bridges older than the origin field only ever answered commands.
    if "origin" not in payload:
        return FeedbackOrigin.REMOTE
    return _parse_enum_field(payload, "origin", FeedbackOrigin)


def _parse_optional_positive_int(payload: dict, key: str) -> int | None:
    if payload.get(key) is None:
        return None

    value = parse_int_field(payload, key)
    if value is None or value <= 0:
        raise ValueError(f"Non-positive or non-integer field: {key}")

    return value


def _parse_optional_run_id(payload: dict) -> UUID | None:
    value = payload.get("run_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Non-string field: run_id")
    try:
        return UUID(value.strip())
    except ValueError:
        raise ValueError(f"Field run_id is not a UUID: {value!r}") from None


def _parse_gait_field(payload: dict) -> GaitMode:
    value = parse_int_field(payload, "gait")

    if value is None:
        raise ValueError("Missing or non-integer field: gait (required while the prosthesis is on)")

    try:
        return GaitMode(value)
    except ValueError:
        raise ValueError(f"Unsupported value for field gait: {value!r}") from None


def _parse_current_field(payload: dict) -> int:
    # Reported, not commanded: no range check here, so a surprising value still gets stored.
    value = parse_int_field(payload, "current")

    if value is None:
        raise ValueError("Missing or non-integer field: current (required while the prosthesis is on)")

    return value


@dataclass(slots=True, init=False)
class CommandFeedbackLog:
    """The bridge's answer to a command, or a report of something the prosthesis did on its own.

    `gait_mode` and `current_limit` are the settings the prosthesis runs with, so they are only
    kept while it is on. `run_id` is the run the feedback belongs to: the one running after the
    command, or, when it left the prosthesis off, the one it ended. `id` is assigned by the
    database when the feedback is stored.
    """

    command_id: int | None
    command: FeedbackCommand
    result_status: ResultStatus
    power_state: ProsthesisPowerState
    gait_mode: GaitMode | None
    current_limit: int | None
    message: str
    origin: FeedbackOrigin
    run_id: UUID | None
    issued_at: datetime
    received_at: datetime
    id: int | None

    def __init__(self, payload: dict) -> None:
        self.received_at = datetime.now(timezone.utc)

        # The bridge sends the moment it produced the feedback as `timestamp`.
        if "timestamp" not in payload:
            raise ValueError("Missing field: timestamp")
        self.issued_at = parse_timestamp(payload.get("timestamp"))

        self.command = _parse_enum_field(payload, "command", FeedbackCommand)
        self.result_status = _parse_enum_field(payload, "status", ResultStatus)
        self.power_state = _parse_enum_field(payload, "state", ProsthesisPowerState)
        self.origin = _parse_origin(payload)

        self.command_id = _parse_optional_positive_int(payload, "command_id")
        if self.origin is FeedbackOrigin.INTERNAL and self.command_id is not None:
            raise ValueError("Internal feedback must not reference a command")

        self.run_id = _parse_optional_run_id(payload)

        if self.power_state is ProsthesisPowerState.ON:
            self.gait_mode = _parse_gait_field(payload)
            self.current_limit = _parse_current_field(payload)
        else:
            self.gait_mode = None
            self.current_limit = None

        message = payload.get("message")
        if not isinstance(message, str):
            raise ValueError("Missing or non-string field: message")
        self.message = message

        self.id = None

    @property
    def is_success(self) -> bool:
        return self.result_status is ResultStatus.SUCCESS

    def generate_validated_message(self) -> str:
        validated_payload = {
            "timestamp": self.issued_at.isoformat(),
            "command_id": self.command_id,
            "origin": self.origin.value,
            "run_id": str(self.run_id) if self.run_id is not None else None,
            "command": self.command.value,
            "status": self.result_status.value,
            "state": self.power_state.value,
            "gait": int(self.gait_mode) if self.gait_mode is not None else None,
            "current": self.current_limit,
            "message": self.message,
        }
        return json.dumps(validated_payload, ensure_ascii=False)
