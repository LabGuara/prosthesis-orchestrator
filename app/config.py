import os
from dataclasses import dataclass
import logging


@dataclass
class Settings:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    MQTT_RAW_TOPIC: str
    MQTT_PARSED_TOPIC: str
    MQTT_ACTIONS_TOPIC: str
    mqtt_qos: int
    mqtt_client_id: str

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    log_level: str


def load_settings() -> Settings:
    return Settings(
        mqtt_host=os.getenv("MQTT_HOST", "localhost"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        mqtt_username=os.getenv("MQTT_USERNAME") or None,
        mqtt_password=os.getenv("MQTT_PASSWORD") or None,
        MQTT_RAW_TOPIC=os.getenv("MQTT_RAW_TOPIC", "prothesis/logs/raw"),
        MQTT_PARSED_TOPIC=os.getenv("MQTT_PARSED_TOPIC", "prothesis/logs/parsed"),
        MQTT_ACTIONS_TOPIC=os.getenv("MQTT_ACTIONS_TOPIC", "prothesis/actions"),
        mqtt_qos=int(os.getenv("MQTT_QOS", "1")),
        mqtt_client_id=os.getenv("MQTT_CLIENT_ID", "prothesis-logger"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "prothesis_logger"),
        db_user=os.getenv("DB_USER", "prothesis_user"),
        db_password=os.getenv("DB_PASSWORD", "prothesis_password"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
