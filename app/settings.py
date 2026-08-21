import os
from dataclasses import dataclass


@dataclass(slots=True, init=False)
class Settings:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_logs_topic: str
    mqtt_logs_parsed_topic: str
    mqtt_command_logs_topic: str
    mqtt_command_logs_parsed_topic: str
    mqtt_power_feedback_topic: str
    mqtt_power_feedback_parsed_topic: str
    mqtt_qos: int
    mqtt_client_id: str
    mqtt_tls: bool

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    log_level: str

    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME") or None
        self.mqtt_password = os.getenv("MQTT_PASSWORD") or None
        self.mqtt_logs_topic = os.getenv("MQTT_LOGS_TOPIC", "prosthesis/logs/raw")
        self.mqtt_logs_parsed_topic = os.getenv("MQTT_LOGS_PARSED_TOPIC", "prosthesis/logs/parsed")
        self.mqtt_command_logs_topic = os.getenv("MQTT_COMMAND_LOGS_TOPIC", "prosthesis/actions")
        self.mqtt_command_logs_parsed_topic = os.getenv("MQTT_COMMAND_LOGS_PARSED_TOPIC", "prosthesis/actions/parsed")
        self.mqtt_power_feedback_topic = os.getenv("MQTT_POWER_FEEDBACK_TOPIC", "prosthesis/actions/feedback")
        self.mqtt_power_feedback_parsed_topic = os.getenv("MQTT_POWER_FEEDBACK_PARSED_TOPIC", "prosthesis/actions/feedback/parsed")
        self.mqtt_qos = int(os.getenv("MQTT_QOS", "1"))
        self.mqtt_client_id = os.getenv("MQTT_CLIENT_ID", "prosthesis-logger")
        self.mqtt_tls = os.getenv("MQTT_TLS", "false").lower() == "true"
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "prosthesis_logger")
        self.db_user = os.getenv("DB_USER", "prosthesis_user")
        self.db_password = os.getenv("DB_PASSWORD", "prosthesis_password")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
