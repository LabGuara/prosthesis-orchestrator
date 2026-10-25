from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime, timezone
import json

from app.utils import parse_int_field, parse_timestamp


MINIMUM_ACTUATOR_CURRENT = 3000
MAXIMUM_ACTUATOR_CURRENT = 15000


class CommandType(IntEnum):
    GAIT_MODE = 1
    POWER = 2
    ACTUATOR_CURRENT = 3


class GaitMode(IntEnum):
    WALKING = 1
    STAIR_ASCENT = 2
    STANDING = 3
    STAIR_DESCENT = 4
    UPSLOPE_WALKING = 5
    DOWNSLOPE_WALKING = 6
    SITTING = 7
    SIT_TO_STAND = 8
    STAND_TO_SIT = 9


class PowerState(IntEnum):
    ON = 1
    OFF = 2


@dataclass(slots=True, frozen=True)
class ActuatorCurrent:
    """Raw actuator current setpoint, not an enum: any value in the accepted range is valid."""

    value: int

    def __post_init__(self) -> None:
        if not MINIMUM_ACTUATOR_CURRENT <= self.value <= MAXIMUM_ACTUATOR_CURRENT:
            raise ValueError(
                f"Actuator current out of range "
                f"({MINIMUM_ACTUATOR_CURRENT}-{MAXIMUM_ACTUATOR_CURRENT}): {self.value}"
            )


Command = GaitMode | PowerState | ActuatorCurrent

COMMAND_PARSERS: dict[CommandType, Callable[[int], Command]] = {
    CommandType.GAIT_MODE: GaitMode,
    CommandType.POWER: PowerState,
    CommandType.ACTUATOR_CURRENT: ActuatorCurrent,
}


def _parse_command_type(payload: dict) -> CommandType:
    value = parse_int_field(payload, "command_type")
    if value is None:
        raise ValueError("Missing or non-integer field: command_type")

    try:
        return CommandType(value)
    except ValueError:
        raise ValueError(f"Unsupported command type: {value}") from None


@dataclass(slots=True, init=False)
class CommandLog:
    """A command as the app issued it. `id` is assigned by the database when it is stored."""

    issued_at: datetime
    received_at: datetime
    command_type: CommandType
    command: Command
    id: int | None

    def __init__(self, payload: dict) -> None:
        self.received_at = datetime.now(timezone.utc)
        # The app sends the moment it issued the command as `timestamp`.
        self.issued_at = parse_timestamp(payload.get("timestamp"))
        self.command_type = _parse_command_type(payload)

        value = parse_int_field(payload, "value")
        if value is None:
            raise ValueError("Missing or non-integer field: value")

        self.command = COMMAND_PARSERS[self.command_type](value)
        self.id = None

    @property
    def value(self) -> int:
        return int(self.command.value)

    def generate_validated_message(self) -> str:
        """The command as the bridge receives it, carrying the id the feedback must echo."""
        if self.id is None:
            raise ValueError("Command must be stored before it is forwarded")

        validated_payload = {
            "command_id": self.id,
            "timestamp": self.issued_at.isoformat(),
            "command_type": int(self.command_type),
            "value": self.value,
        }
        return json.dumps(validated_payload)
