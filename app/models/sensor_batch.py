from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from uuid import UUID


TIME_KEY = "t"


@dataclass(slots=True, frozen=True)
class SensorSample:
    t: float
    sensor_data: dict

    @property
    def t_ms(self) -> int:
        return math.floor(self.t * 1000 + 0.5)

    def as_reading(self) -> dict:
        return {TIME_KEY: self.t, **self.sensor_data}


def _parse_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    t = float(value)
    return t if math.isfinite(t) else None


def _extract_readings(data: object) -> list:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("Sensor data is not valid JSON") from None

    if isinstance(data, dict) and isinstance(data.get("value"), list):
        data = data["value"]

    if not isinstance(data, list):
        raise ValueError("Sensor data must be an array of readings")

    return data


@dataclass(slots=True, init=False)
class SensorBatch:
    received_at: datetime
    samples: list[SensorSample]
    discarded: int

    def __init__(self, payload: dict) -> None:
        self.received_at = datetime.now(timezone.utc)

        if "data" not in payload:
            raise ValueError("Missing field: data")
        readings = _extract_readings(payload["data"])

        self.samples = []
        self.discarded = 0
        for reading in readings:
            t = _parse_time(reading.get(TIME_KEY)) if isinstance(reading, dict) else None
            if t is None:
                self.discarded += 1
                continue
            sensor_data = {key: value for key, value in reading.items() if key != TIME_KEY}
            self.samples.append(SensorSample(t=t, sensor_data=sensor_data))

        if not self.samples:
            raise ValueError("Batch has no reading with a numeric clock value")

    def generate_validated_message(self, run_id: UUID | None) -> str:
        validated_payload = {
            "run_id": str(run_id) if run_id is not None else None,
            "value": [sample.as_reading() for sample in self.samples],
        }
        return json.dumps(validated_payload, ensure_ascii=False)
