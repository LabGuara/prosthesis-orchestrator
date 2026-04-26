from datetime import datetime, timezone
import json
import uuid


def parse_int_field(payload: dict, key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def parse_timestamp(value: object) -> datetime:
    if isinstance(value, bool):
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    return datetime.now(timezone.utc)


def decode_payload(payload_bytes: bytes) -> dict:
    decoded_text = payload_bytes.decode("utf-8", errors="replace")

    try:
        parsed = json.loads(decoded_text)
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": decoded_text}


def generate_id() -> str:
    return str(uuid.uuid4())
