"""Utility for publishing messages to RabbitMQ queue for testing."""

import json
import logging
import pika
from typing import Dict, Any

from src.config import settings

logger = logging.getLogger(__name__)


class ReviewMessagePublisher:
    """Publisher for sending review requests to RabbitMQ."""
    
    def __init__(self):
        self.connection = None
        self.channel = None
    
    def connect(self):
        """Establish connection to RabbitMQ."""
        try:
            connection_params = pika.URLParameters(settings.rabbitmq_url)
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Declare the queue (creates if doesn't exist)
            self.channel.queue_declare(queue=settings.queue_name, durable=True)
            
            logger.info(f"✅ Connected to RabbitMQ queue: {settings.queue_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def publish_review_request(self, message_data: Dict[str, Any]) -> None:
        """Publish a review request to the queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")
        
        try:
            # Validate required fields
            required_fields = ['repo_url', 'original_pr_url', 'branch', 'modified_files']
            for field in required_fields:
                if field not in message_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Publish the message
            message_body = json.dumps(message_data)
            self.channel.basic_publish(
                exchange='',
                routing_key=settings.queue_name,
                body=message_body,
                properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
            )
            
            logger.info(f"📤 Published review request for: {message_data['repo_url']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to publish message: {e}")
            raise
    
    def close(self):
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


def publish_example_message():
    """Publish an example message for testing."""
    publisher = ReviewMessagePublisher()
    
    try:
        publisher.connect()
        
        # Example message
        example_message = {
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
        
        publisher.publish_review_request(example_message)
        logger.info("✅ Example message published successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to publish example message: {e}")
    finally:
        publisher.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    publish_example_message()