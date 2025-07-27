"""RabbitMQ consumer for processing code review requests."""

import asyncio
import json
import logging
import pika
import sys
from typing import Dict, Any

from src.config import settings
from src.core.review import run_review_graph

logger = logging.getLogger(__name__)


class ReviewQueueConsumer:
    """Consumer that processes code review requests from RabbitMQ."""
    
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
            
            # Set QoS to process one message at a time
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info(f"✅ Connected to RabbitMQ queue: {settings.queue_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def process_message(self, ch, method, properties, body):
        """Process a single message from the queue."""
        try:
            # Parse the message
            message_data = json.loads(body.decode('utf-8'))
            logger.info(f"📨 Processing review request: {message_data.get('repo_url', 'unknown')}")
            
            # Validate required fields
            required_fields = ['repo_url', 'original_pr_url', 'branch', 'modified_files']
            for field in required_fields:
                if field not in message_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Run the review asynchronously
            result = asyncio.run(self._run_review_async(message_data))
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info("✅ Review completed successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except ValueError as e:
            logger.error(f"❌ Invalid message format: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except Exception as e:
            logger.error(f"❌ Error processing review: {e}", exc_info=True)
            # Requeue the message for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    async def _run_review_async(self, message_data: Dict[str, Any]) -> str:
        """Run the review graph asynchronously."""
        return await run_review_graph(
            repo_url=message_data['repo_url'],
            original_pr_url=message_data['original_pr_url'],
            base_branch=message_data['branch'],
            modified_files=json.dumps(message_data['modified_files'])
        )
    
    def start_consuming(self):
        """Start consuming messages from the queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")
        
        self.channel.basic_consume(
            queue=settings.queue_name,
            on_message_callback=self.process_message
        )
        
        logger.info("🔄 Starting to consume messages. Press CTRL+C to exit...")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("🛑 Stopping consumer...")
            self.channel.stop_consuming()
            self.connection.close()
    
    def close(self):
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


def start_queue_worker():
    """Entry point for the queue worker."""
    if not settings.github_token:
        logger.error("❌ GITHUB_TOKEN is unset or empty")
        sys.exit(1)
    
    consumer = ReviewQueueConsumer()
    
    try:
        consumer.connect()
        consumer.start_consuming()
    except Exception as e:
        logger.error(f"❌ Queue worker failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        consumer.close()