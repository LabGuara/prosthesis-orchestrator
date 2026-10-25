import logging

from dotenv import load_dotenv

load_dotenv()

from app.settings import Settings
from app.services.database_service import DatabaseService
from app.models.command_log import CommandLog
from app.models.command_feedback_log import CommandFeedbackLog
from app.models.sensor_batch import SensorBatch
from app.services.mqtt_service import MqttService
from app.utils import configure_logging, decode_payload


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    database_service = DatabaseService(settings)
    database_service.connect()

    mqtt_service: MqttService | None = None
    # Warn once when readings arrive with no run in progress, not on every batch.
    warned_no_run = False

    def publish(topic: str, payload: str) -> None:
        if mqtt_service is not None:
            mqtt_service.publish(topic, payload)
            logging.debug("Published message to topic=%s", topic)

    def handle_command(payload: dict) -> None:
        try:
            command_log = CommandLog(payload=payload)
        except ValueError as error:
            logging.error("Discarded malformed command: %s", error)
            return

        command_id = database_service.insert_command_log(command_log)
        logging.info(
            "Stored command id=%s command_type=%s value=%s",
            command_id,
            command_log.command_type.name,
            command_log.value,
        )

        publish(settings.mqtt_command_logs_validated_topic, command_log.generate_validated_message())

    def handle_command_feedback(payload: dict) -> None:
        try:
            feedback = CommandFeedbackLog(payload=payload)
        except ValueError as error:
            logging.error("Discarded malformed command feedback: %s", error)
            return

        feedback_id = database_service.insert_command_feedback_log(feedback)
        logging.info(
            "Stored command feedback id=%s command_id=%s origin=%s command=%s status=%s "
            "state=%s gait=%s current=%s run_id=%s",
            feedback_id,
            feedback.command_id,
            feedback.origin.value,
            feedback.command.value,
            feedback.result_status.value,
            feedback.power_state.value,
            feedback.gait_mode.name if feedback.gait_mode is not None else None,
            feedback.current_limit,
            feedback.run_id,
        )

        publish(settings.mqtt_power_feedback_validated_topic, feedback.generate_validated_message())

    def handle_sensor_batch(payload: dict) -> None:
        nonlocal warned_no_run

        try:
            batch = SensorBatch(payload=payload)
        except ValueError as error:
            logging.warning("Discarded sensor batch: %s", error)
            return

        if batch.discarded:
            logging.warning(
                "Dropped %s reading(s) without a numeric clock value", batch.discarded
            )

        run_id, inserted = database_service.insert_sensor_batch(batch)
        if run_id is None:
            if not warned_no_run:
                logging.warning(
                    "Sensor readings arrived with no run in progress; they are not stored "
                    "until a feedback starts a run"
                )
                warned_no_run = True
        else:
            warned_no_run = False
            logging.debug(
                "Stored %s of %s sample(s) for run %s", inserted, len(batch.samples), run_id
            )

        publish(settings.mqtt_logs_validated_topic, batch.generate_validated_message(run_id))

    def handle_message(topic: str, payload_bytes: bytes) -> None:
        payload = decode_payload(payload_bytes)

        try:
            if topic == settings.mqtt_command_logs_topic:
                handle_command(payload)
            elif topic == settings.mqtt_power_feedback_topic:
                handle_command_feedback(payload)
            elif topic == settings.mqtt_logs_topic:
                handle_sensor_batch(payload)
            else:
                logging.warning("Ignoring message on unexpected topic=%s", topic)
        except Exception:
            # A failed write is logged and the message dropped; the consumer keeps running.
            logging.exception("Failed to handle message from topic=%s", topic)

    mqtt_service = MqttService(settings=settings, on_message_received=handle_message)

    logging.info("Starting MQTT consumer...")

    try:
        mqtt_service.run_forever()
    finally:
        database_service.close()


if __name__ == "__main__":
    main()
