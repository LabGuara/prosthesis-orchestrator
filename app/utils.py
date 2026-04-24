import json
import uuid
from app.gait_mode import GaitMode



def decode_payload(payload_bytes: bytes) -> dict:
    decoded_text = payload_bytes.decode("utf-8", errors="replace")

    try:
        parsed = json.loads(decoded_text)
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": decoded_text}


def parse_int_field(payload: dict, key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def parse_numeric_field(payload: dict, key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def pick_message_id(payload: dict) -> str:
    payload_id = payload.get("id")
    if isinstance(payload_id, str) and payload_id.strip():
        return payload_id

    return str(uuid.uuid4())


def build_action_message(action_value: int) -> str:
    try:
        action = GaitMode(action_value)
        mode_name = action.name.replace("_", " ").title()
    except ValueError:
        mode_name = f"unknown mode ({action_value})"
    return f"Gait mode changed to {mode_name}"