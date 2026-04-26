import logging

from app.config import configure_logging, load_settings
from app.services.database_service import DatabaseService
from app.models.command_log import CommandLog, GaitMode
from app.models.log import Log
from app.services.mqtt_service import MqttService
from app.utils import decode_payload, generate_id


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    database_service = DatabaseService(settings)
    database_service.connect()

    mqtt_service: MqttService | None = None

    def handle_message(topic: str, payload_bytes: bytes) -> None:
        payload = decode_payload(payload_bytes)
        message_id = generate_id()

        parsed_message_payload = ""

        if topic == settings.MQTT_ACTIONS_TOPIC:
            command_log = CommandLog(id=message_id, payload=payload)
            database_service.insert_command_log(command_log)
            parsed_message_payload = command_log.generate_parsed_log_message()
            logging.info("Stored command log from topic=%s id=%s", topic, message_id)
        else:
            log_entry = Log(message_id, payload)
            database_service.insert_log(log_entry)
            parsed_message_payload = log_entry.generate_parsed_log_message()
            logging.info("Stored message from topic=%s id=%s", topic, message_id)

        if mqtt_service is not None:
            mqtt_service.publish(settings.MQTT_PARSED_TOPIC, parsed_message_payload)
            logging.info(
                "Published parsed message to topic=%s", settings.MQTT_PARSED_TOPIC
            )

    mqtt_service = MqttService(settings=settings, on_message_received=handle_message)

    logging.info("Starting MQTT consumer...")

    try:
        mqtt_service.run_forever()
    finally:
        database_service.close()


if __name__ == "__main__":
    main()