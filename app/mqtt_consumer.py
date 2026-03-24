import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt

from app.config import Settings


class MqttConsumer:
    def __init__(
        self,
        settings: Settings,
        on_message_received: Callable[[str, bytes], None],
    ) -> None:
        self._settings = settings
        self._on_message_received = on_message_received

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
        )

        if settings.mqtt_username:
            self._client.username_pw_set(
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            )

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata,
        flags,
        reason_code,
        properties,
    ) -> None:
        if reason_code != 0:
            logging.error("MQTT connect failed. reason_code=%s", reason_code)
            return

        topics = [*self._settings.MQTT_RAW_TOPIC, self._settings.MQTT_ACTIONS_TOPIC]
        for topic in topics:
            client.subscribe(topic, qos=self._settings.mqtt_qos)
            logging.info("Subscribed to topic: %s", topic)

    def _on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        self._on_message_received(message.topic, message.payload)

    def publish(self, topic: str, payload: str) -> None:
        result = self._client.publish(topic, payload=payload, qos=self._settings.mqtt_qos)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logging.error("Failed to publish parsed message. topic=%s rc=%s", topic, result.rc)

    def run_forever(self) -> None:
        self._client.connect(
            host=self._settings.mqtt_host,
            port=self._settings.mqtt_port,
            keepalive=60,
        )
        self._client.loop_forever(retry_first_connection=True)
