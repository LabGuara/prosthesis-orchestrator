from datetime import datetime, timezone
import json
import logging
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
    now_utc = datetime.now(timezone.utc)

    if isinstance(value, bool):
        return now_utc

    if isinstance(value, (int, float)):
        ts = float(value)
        # If timestamp appears to be in seconds, normalize to milliseconds.
        if ts < 1e12:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)

    if isinstance(value, str):
        raw_value = value.strip()
        if not raw_value:
            return now_utc

        # Accept numeric timestamps encoded as strings.
        try:
            numeric_ts = float(raw_value)
            if numeric_ts < 1e12:
                return datetime.fromtimestamp(numeric_ts, tz=timezone.utc)
            return datetime.fromtimestamp(numeric_ts / 1000.0, tz=timezone.utc)
        except ValueError:
            pass

        # Accept ISO 8601 values, including `Z` suffix for UTC.
        try:
            parsed_dt = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            if parsed_dt.tzinfo is None:
                return parsed_dt.replace(tzinfo=timezone.utc)
            return parsed_dt.astimezone(timezone.utc)
        except ValueError:
            return now_utc

    return now_utc


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

def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )