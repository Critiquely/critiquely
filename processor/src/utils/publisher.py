"""Utility for publishing messages to RabbitMQ queue for testing."""

import logging
from typing import Dict, Any

from src.queue.rabbitmq import RabbitMQClient, rabbitmq_client, create_example_message

logger = logging.getLogger(__name__)


class ReviewMessagePublisher:
    """Publisher for sending review requests to RabbitMQ."""
    
    def __init__(self):
        self.client = RabbitMQClient()
    
    def connect(self):
        """Establish connection to RabbitMQ."""
        self.client.connect()
    
    def publish_review_request(self, message_data: Dict[str, Any]) -> None:
        """Publish a review request to the queue."""
        self.client.publish_review_request(message_data)
    
    def close(self):
        """Close the connection to RabbitMQ."""
        self.client.close()


def publish_example_message():
    """Publish an example message for testing using context manager."""
    try:
        with rabbitmq_client() as client:
            example_message = create_example_message()
            client.publish_review_request(example_message)
            logger.info("✅ Example message published successfully")
            
    except Exception as e:
        logger.error(f"❌ Failed to publish example message: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    publish_example_message()