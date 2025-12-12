"""Consumer for processing code review requests from RabbitMQ."""

import asyncio
import json
import logging
from typing import Any, Dict

from src.config import settings
from src.graph.graph import run_graph
from src.queue.rabbitmq import RabbitMQClient

logger = logging.getLogger(__name__)


class ReviewQueueConsumer:
    """Consumer that processes code review requests from RabbitMQ."""

    def __init__(self):
        self.client = RabbitMQClient()

    def process_message(self, ch, method, properties, body):
        """Process a single code review message from the queue.

        Args:
            ch: RabbitMQ channel object.
            method: Delivery method containing delivery_tag for acknowledgment.
            properties: Message properties (unused).
            body: Raw message body bytes containing review request data.

        Note:
            - On success: Message is acknowledged (ack) and removed from queue.
            - On ValueError: Message is rejected (nack) without requeue (dead letter).
            - On other Exception: Message is rejected (nack) with requeue for retry.
        """
        try:
            # Parse and validate the message
            message_data = self.client.parse_message(body)
            logger.info(
                f"📨 Processing review request: {message_data.get('repo_url', 'unknown')}"
            )

            # Run the review asynchronously
            result = asyncio.run(self.run_review_async(message_data))

            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info("✅ Review completed successfully")

        except ValueError as e:
            logger.error(f"❌ Invalid message format: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:
            logger.error(f"❌ Error processing review: {e}", exc_info=True)
            # Requeue the message for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    async def run_review_async(self, message_data: Dict[str, Any]):
        """Execute the LangGraph code review workflow asynchronously.

        Args:
            message_data: Dictionary containing:
                - repo_url: GitHub repository URL
                - original_pr_url: Pull request URL
                - branch: Branch name to review
                - modified_files: List of modified files

        Returns:
            Result from the run_graph execution.

        Note:
            This wraps the async run_graph function and handles the JSON
            serialization of modified_files.
        """
        return await run_graph(
            repo_url=message_data["repo_url"],
            original_pr_url=message_data["original_pr_url"],
            base_branch=message_data["branch"],
            modified_files=json.dumps(message_data["modified_files"]),
        )
        logger.info(f"🔄 Would process: {message_data['repo_url']}")
        return "Review completed (placeholder)"

    def start_consuming(self):
        """Initialize and start the consumer (blocking operation).

        Connects to RabbitMQ, sets up the consumer with the process_message
        callback, and begins consuming messages from the queue.

        Note:
            This is a blocking call that runs indefinitely until interrupted.
        """
        self.client.connect()
        self.client.setup_consumer(self.process_message)
        self.client.start_consuming()

    def close(self):
        """Close the RabbitMQ connection and cleanup resources.

        Note:
            Should be called in a finally block to ensure cleanup occurs
            even if an error is raised.
        """
        self.client.close()
