"""RabbitMQ client for consuming and publishing code review messages."""

import json
import logging
from typing import Any, Callable, Dict

import pika

from src.config import settings

logger = logging.getLogger(__name__)

REQUIRED_MESSAGE_FIELDS = ["repo_url", "original_pr_url", "branch", "modified_files"]


class RabbitMQClient:
    """RabbitMQ client with connection management and message validation."""

    def __init__(self):
        self.connection = None
        self.channel = None

    def connect(self):
        """Establish connection to RabbitMQ."""
        try:
            connection_params = pika.URLParameters(settings.rabbitmq_url)
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=settings.queue_name, durable=True)
            logger.info(f"✅ Connected to RabbitMQ queue: {settings.queue_name}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise

    def parse_message(self, body: bytes) -> Dict[str, Any]:
        """Parse and validate message body."""
        try:
            message_data = json.loads(body.decode("utf-8"))
            missing = [f for f in REQUIRED_MESSAGE_FIELDS if f not in message_data]
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")
            return message_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message: {e}")

    def publish_review_request(self, message_data: Dict[str, Any]):
        """Publish a review request to the queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        try:
            missing = [f for f in REQUIRED_MESSAGE_FIELDS if f not in message_data]
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            message_body = json.dumps(message_data)
            self.channel.basic_publish(
                exchange="",
                routing_key=settings.queue_name,
                body=message_body,
                properties=pika.BasicProperties(delivery_mode=2),
            )
            logger.info(f"📤 Published review request for: {message_data['repo_url']}")
        except Exception as e:
            logger.error(f"❌ Failed to publish message: {e}")
            raise

    def setup_consumer(self, message_handler: Callable):
        """Setup consumer with message handler."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=settings.queue_name, on_message_callback=message_handler
        )

    def start_consuming(self):
        """Start consuming messages from the queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        logger.info("🔄 Waiting for messages. Press CTRL+C to exit...")

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("🛑 Stopping consumer...")
            self.stop_consuming()

    def stop_consuming(self):
        """Stop consuming messages."""
        if self.channel:
            self.channel.stop_consuming()

    def close(self):
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("🔌 Disconnected from RabbitMQ")
