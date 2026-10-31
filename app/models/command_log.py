from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime, timezone
import json
import logging
from uuid import UUID

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


def _parse_collect_id(payload: dict) -> UUID | None:
    """The collect is only bookkeeping, so a malformed one is dropped with a warning rather
    than the command: a stop must never be discarded over it."""
    value = payload.get("collect_id")
    if value is None:
        return None

    if isinstance(value, str):
        try:
            return UUID(value.strip())
        except ValueError:
            pass

    logging.warning("Ignoring malformed collect_id %r; the command is kept", value)
    return None


@dataclass(slots=True, init=False)
class CommandLog:
    """A command as the app issued it. `collect_id` is the collect the app had open,
    if any: it is not stored with the command, only passed on to the bridge, which reports it back
    on the feedback of the run the command starts. `id` is assigned by the database when it is
    stored."""

    issued_at: datetime
    received_at: datetime
    command_type: CommandType
    command: Command
    collect_id: UUID | None
    id: int | None

    def __init__(self, payload: dict) -> None:
        self.received_at = datetime.now(timezone.utc)
        self.issued_at = parse_timestamp(payload.get("timestamp"))
        self.command_type = _parse_command_type(payload)

        value = parse_int_field(payload, "value")
        if value is None:
            raise ValueError("Missing or non-integer field: value")

        self.command = COMMAND_PARSERS[self.command_type](value)
        self.collect_id = _parse_collect_id(payload)
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
            "collect_id": str(self.collect_id) if self.collect_id is not None else None,
        }
        return json.dumps(validated_payload)
