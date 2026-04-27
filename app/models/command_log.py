from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime
import json

from app.models.log_level import LogLevel
from app.utils import parse_int_field, parse_timestamp


class CommandType(IntEnum):
    GAIT_MODE = 1


class GaitMode(IntEnum):
    STAND_UP = 1
    WALK = 2
    CLIMB_STAIRS = 3

    def build_gate_mode_action_message(self) -> str:
        mode_name = self.name.replace("_", " ").title()
        return f"Gait mode changed to {mode_name}"


Command = GaitMode


@dataclass(init=False)
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
            case _:
                raise ValueError(f"Unsupported command type: {command_type}")

    def generate_parsed_log_message(self) -> str:
        message = ""
        if isinstance(self.command, GaitMode):
            message = self.command.build_gate_mode_action_message()

        return json.dumps(
            {
                "level": LogLevel.INFO,
                "timestamp": self.timestamp.isoformat(),
                "sensor_name": "command",
                "message": message,
            }
        )
