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
        """Establish connection to RabbitMQ and declare the queue.

        Raises:
            Exception: If connection fails or queue declaration fails.

        Note:
            The queue is declared as durable to survive broker restarts.
        """
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
        """Parse and validate message body from queue.

        Args:
            body: Raw message body bytes from RabbitMQ.

        Returns:
            Parsed message data as a dictionary containing at least:
            - repo_url
            - original_pr_url
            - branch
            - modified_files

        Raises:
            ValueError: If JSON is invalid or required fields are missing.
        """
        try:
            message_data = json.loads(body.decode("utf-8"))
            missing = [f for f in REQUIRED_MESSAGE_FIELDS if f not in message_data]
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")
            return message_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message: {e}")

    def publish_review_request(self, message_data: Dict[str, Any]):
        """Publish a code review request to the queue.

        Args:
            message_data: Dictionary containing review request data.
                         Must include: repo_url, original_pr_url, branch, modified_files.

        Raises:
            RuntimeError: If not connected to RabbitMQ.
            ValueError: If required fields are missing from message_data.
            Exception: If message publishing fails.

        Note:
            Messages are published with delivery_mode=2 (persistent) to ensure
            they survive broker restarts.
        """
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
        """Configure the consumer with a message handler callback.

        Args:
            message_handler: Callback function with signature:
                           (channel, method, properties, body) -> None

        Raises:
            RuntimeError: If not connected to RabbitMQ.

        Note:
            Sets prefetch_count=1 to process one message at a time,
            ensuring even distribution across multiple workers.
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=settings.queue_name, on_message_callback=message_handler
        )

    def start_consuming(self):
        """Start consuming messages from the queue (blocking operation).

        Raises:
            RuntimeError: If not connected to RabbitMQ.

        Note:
            This is a blocking call that runs until interrupted with KeyboardInterrupt.
            Gracefully handles CTRL+C by calling stop_consuming().
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        logger.info("🔄 Waiting for messages. Press CTRL+C to exit...")

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("🛑 Stopping consumer...")
            self.stop_consuming()

    def stop_consuming(self):
        """Stop consuming messages from the queue.

        Note:
            Safe to call even if no consumer is active.
        """
        if self.channel:
            self.channel.stop_consuming()

    def close(self):
        """Close the connection to RabbitMQ.

        Note:
            Safe to call even if connection is already closed.
            Only closes if connection exists and is not already closed.
        """
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("🔌 Disconnected from RabbitMQ")
