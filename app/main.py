import logging
import json
import uuid

from app.config import load_settings
from app.db import Database, decode_payload
from app.mqtt_consumer import MqttConsumer


ACTION_VALUE_TO_NAME = {
    1: "Stand up",
    2: "Walk",
    3: "Climb stairs",
}


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def pick_message_id(payload: dict) -> str:
    payload_id = payload.get("id")
    if isinstance(payload_id, str) and payload_id.strip():
        return payload_id

    return str(uuid.uuid4())


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


def build_action_message(action_value: int) -> str:
    mode_name = ACTION_VALUE_TO_NAME.get(action_value, f"unknown mode ({action_value})")
    return f"Gait mode changed to {mode_name}"


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    db = Database(settings)
    db.connect()

    consumer: MqttConsumer | None = None

    def handle_message(topic: str, payload_bytes: bytes) -> None:
        payload = decode_payload(payload_bytes)
        message_id = pick_message_id(payload)

        if topic == settings.MQTT_ACTIONS_TOPIC:
            command_type = parse_int_field(payload, "commandType")
            action_value_number = parse_numeric_field(payload, "value")

            if command_type is None or action_value_number is None:
                logging.error(
                    "Invalid action payload on topic=%s id=%s payload=%s",
                    topic,
                    message_id,
                    payload,
                )
                return

            db.insert_command_log(
                message_id=message_id,
                command_type=command_type,
                value=action_value_number,
            )
            logging.info("Stored command log from topic=%s id=%s", topic, message_id)

            action_value = int(action_value_number) if action_value_number.is_integer() else -1
            parsed_action_log = {
                "level": "normal",
                "sensor_type": "action",
                "sensor_name": "action-01",
                "message": build_action_message(action_value),
            }

            if consumer is not None:
                consumer.publish(settings.MQTT_PARSED_TOPIC, json.dumps(parsed_action_log))
                logging.info("Published parsed action to topic=%s", settings.MQTT_PARSED_TOPIC)

            return

        db.insert_log(message_id=message_id, payload=payload)
        logging.info("Stored message from topic=%s id=%s", topic, message_id)

        if consumer is not None:
            consumer.publish(settings.MQTT_PARSED_TOPIC, json.dumps(payload))
            logging.info("Published parsed message to topic=%s", settings.MQTT_PARSED_TOPIC)

    consumer = MqttConsumer(settings=settings, on_message_received=handle_message)

    logging.info("Starting MQTT consumer...")
    try:
        consumer.run_forever()
    finally:
        db.close()


if __name__ == "__main__":
    main()