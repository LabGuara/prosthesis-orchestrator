from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime

from app.models.log_level import LogLevel
from app.models.parsed_log import ParsedLog
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

    def build_gate_mode_action_message(self) -> str:
        return str(self.value)


class PowerState(IntEnum):
    ON = 16
    OFF = 17

    def build_power_action_message(self) -> str:
        return str(self.value)


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

    def build_actuator_current_action_message(self) -> str:
        return str(self.value)


Command = GaitMode | PowerState | ActuatorCurrent


@dataclass(slots=True, init=False)
class CommandLog:
    id: str
    timestamp: datetime
    command: Command

    def __init__(self, id: str, payload: dict) -> None:
        self.id = id
        self.timestamp = parse_timestamp(payload.get("timestamp"))

        command_type = parse_int_field(payload, "command_type")

        match command_type:
            case CommandType.GAIT_MODE:
                self.command = GaitMode(parse_int_field(payload, "value"))
            case CommandType.POWER:
                self.command = PowerState(parse_int_field(payload, "value"))
            case CommandType.ACTUATOR_CURRENT:
                actuator_current = parse_int_field(payload, "value")
                if actuator_current is None:
                    raise ValueError("Missing or non-integer actuator current value")
                self.command = ActuatorCurrent(actuator_current)
            case _:
                raise ValueError(f"Unsupported command type: {command_type}")

    def generate_parsed_log_message(self) -> str:
        message = ""
        if isinstance(self.command, GaitMode):
            message = self.command.build_gate_mode_action_message()
        elif isinstance(self.command, PowerState):
            message = self.command.build_power_action_message()
        elif isinstance(self.command, ActuatorCurrent):
            message = self.command.build_actuator_current_action_message()

        parsed_log = ParsedLog(
            level=LogLevel.INFO,
            timestamp=self.timestamp,
            sensor_name="command",
            message=message,
        )
        return parsed_log.generate_parsed_log_message()
