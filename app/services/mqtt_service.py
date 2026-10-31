import logging
import uuid
from collections.abc import Callable
from paho.mqtt.enums import CallbackAPIVersion
import paho.mqtt.client as mqtt
from app.settings import Settings


class MqttService:
    def __init__(
        self,
        settings: Settings,
        on_message_received: Callable[[str, bytes], None],
    ) -> None:
        self._settings = settings
        self._on_message_received = on_message_received
        self._client_id = self._build_unique_client_id()

        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
        )

        logging.info("Using MQTT client_id: %s", self._client_id)

        if settings.mqtt_username:
            self._client.username_pw_set(
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            )

        self._configure_tls()

        # Enable paho debug logging and bind optional callbacks
        self._client.enable_logger()
        self._client.on_disconnect = self._on_disconnect
        self._client.on_log = self._on_log

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _build_unique_client_id(self) -> str:
        base = self._settings.mqtt_client_id or "prosthesis-orchestrator"
        suffix = uuid.uuid4().hex[:8]
        return f"{base[:14]}-{suffix}"
    
    def _configure_tls(self) -> None:
        """
        Configure TLS settings based on MQTT_TLS environment variable and port.

        TLS is enabled if MQTT_TLS environment variable is set to 'true'
        """

        if self._settings.mqtt_tls:
            self._client.tls_set()
            logging.info("TLS enabled for MQTT connection")
            
    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata,
        _flags,
        reason_code,
        _properties,
    ) -> None:
        if reason_code != 0:
            logging.error("MQTT connect failed. reason_code=%s", reason_code)
            return

        topics = (
            self._settings.mqtt_logs_topic,
            self._settings.mqtt_command_logs_topic,
            self._settings.mqtt_power_feedback_topic,
            self._settings.mqtt_collects_topic,
        )
        for topic in topics:
            client.subscribe(topic, qos=self._settings.mqtt_qos)
            logging.info("Subscribed to topic: %s", topic)

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata,
        _flags,
        reason_code,
        _properties,
    ) -> None:
        logging.warning("MQTT disconnected. reason_code=%s", reason_code)

    def _on_log(self, _client: mqtt.Client, _userdata, _level, buf: str) -> None:
        logging.debug("paho-mqtt: %s", buf)

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata,
        message: mqtt.MQTTMessage
    ) -> None:
        self._on_message_received(message.topic, message.payload)

    def publish(
        self,
        topic: str,
        payload: str
    ) -> None:
        result = self._client.publish(
            topic,
            payload=payload,
            qos=self._settings.mqtt_qos
        )
        
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logging.error("Failed to publish validated message. topic=%s rc=%s", topic, result.rc)

    def run_forever(self) -> None:
        self._client.connect(
            host=self._settings.mqtt_host,
            port=self._settings.mqtt_port,
            keepalive=60,
        )
        
        self._client.loop_forever(retry_first_connection=True)
