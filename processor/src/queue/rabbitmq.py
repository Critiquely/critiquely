"""Unified RabbitMQ client for both consuming and publishing messages."""

import json
import logging
import pika
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager

from src.config import settings

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """Unified RabbitMQ client with connection management and retry logic."""
    
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self._required_fields = ['repo_url', 'original_pr_url', 'branch', 'modified_files']
    
    def connect(self) -> None:
        """Establish connection to RabbitMQ with error handling."""
        try:
            connection_params = pika.URLParameters(settings.rabbitmq_url)
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Setup queue with consistent configuration
            self._setup_queue()
            
            logger.info(f"✅ Connected to RabbitMQ queue: {settings.queue_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def _setup_queue(self) -> None:
        """Setup default queue with consistent configuration."""
        if not self.channel:
            raise RuntimeError("Channel not available")

        # Declare the default queue (creates if doesn't exist)
        self.channel.queue_declare(queue=settings.queue_name, durable=True)

    def declare_queue(self, queue_name: str) -> None:
        """Declare a queue (creates if doesn't exist).

        Args:
            queue_name: Name of the queue to declare.
        """
        if not self.channel:
            raise RuntimeError("Channel not available")

        self.channel.queue_declare(queue=queue_name, durable=True)
    
    def _validate_message(self, message_data: Dict[str, Any]) -> None:
        """Validate message contains required fields."""
        for field in self._required_fields:
            if field not in message_data:
                raise ValueError(f"Missing required field: {field}")
    
    def publish_review_request(self, message_data: Dict[str, Any]) -> None:
        """Publish a review request to the queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")
        
        try:
            self._validate_message(message_data)
            
            message_body = json.dumps(message_data)
            self.channel.basic_publish(
                exchange='',
                routing_key=settings.queue_name,
                body=message_body,
                properties=pika.BasicProperties(delivery_mode=2)  # Persistent messages
            )
            
            logger.info(f"📤 Published review request for: {message_data['repo_url']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to publish message: {e}")
            raise
    
    def setup_consumer(self, message_handler: Callable) -> None:
        """Setup consumer with message handler for the default queue."""
        self.setup_consumer_for_queue(settings.queue_name, message_handler)

    def setup_consumer_for_queue(
        self, queue_name: str, message_handler: Callable
    ) -> None:
        """Setup consumer with message handler for a specific queue.

        Args:
            queue_name: Name of the queue to consume from.
            message_handler: Callback function to handle messages.
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        # Set QoS to process one message at a time
        self.channel.basic_qos(prefetch_count=1)

        # Setup consumer
        self.channel.basic_consume(
            queue=queue_name, on_message_callback=message_handler
        )
    
    def start_consuming(self) -> None:
        """Start consuming messages from the queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")
        
        logger.info("🔄 Starting to consume messages. Press CTRL+C to exit...")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("🛑 Stopping consumer...")
            self.stop_consuming()
    
    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        if self.channel:
            self.channel.stop_consuming()
    
    def parse_message(self, body: bytes) -> Dict[str, Any]:
        """Parse and validate message body."""
        try:
            message_data = json.loads(body.decode('utf-8'))
            self._validate_message(message_data)
            return message_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message: {e}")
    
    def close(self) -> None:
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("🔌 Disconnected from RabbitMQ")
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return (
            self.connection is not None 
            and not self.connection.is_closed 
            and self.channel is not None
        )


@contextmanager
def rabbitmq_client():
    """Context manager for RabbitMQ client with automatic cleanup."""
    client = RabbitMQClient()
    try:
        client.connect()
        yield client
    finally:
        client.close()


def create_example_message() -> Dict[str, Any]:
    """Create an example message for testing."""
    return {
        "repo_url": "https://github.com/example/repo",
        "original_pr_url": "https://github.com/example/repo/pull/123",
        "branch": "feature-branch",
        "modified_files": [
            {
                "filename": "src/example.py",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "patch": "@@ -1,3 +1,3 @@\n-old line\n+new line"
            }
        ]
    }