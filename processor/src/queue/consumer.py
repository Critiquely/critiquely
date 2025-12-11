"""Consumer for processing code review requests from RabbitMQ."""

import asyncio
import json
import logging
import sys
from typing import Any, Dict

from src.config import settings
from src.queue.rabbitmq import RabbitMQClient

# from src.core.review import run_review_graph

logger = logging.getLogger(__name__)


class ReviewQueueConsumer:
    """Consumer that processes code review requests from RabbitMQ."""

    def __init__(self):
        self.client = RabbitMQClient()

    def process_message(self, ch, method, properties, body):
        """Process a single message from the queue."""
        try:
            # Parse and validate the message
            message_data = self.client.parse_message(body)
            logger.info(
                f"📨 Processing review request: {message_data.get('repo_url', 'unknown')}"
            )

            # Run the review asynchronously
            result = asyncio.run(self._run_review_async(message_data))

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

    async def _run_review_async(self, message_data: Dict[str, Any]):
        """Run the review graph asynchronously."""
        # Uncomment when run_review_graph is available
        # return await run_review_graph(
        #     repo_url=message_data["repo_url"],
        #     original_pr_url=message_data["original_pr_url"],
        #     base_branch=message_data["branch"],
        #     modified_files=json.dumps(message_data["modified_files"]),
        # )
        # Placeholder for now
        logger.info(f"🔄 Would process: {message_data['repo_url']}")
        return "Review completed (placeholder)"

    def start_consuming(self):
        """Start consuming messages from the queue."""
        self.client.connect()
        self.client.setup_consumer(self.process_message)
        self.client.start_consuming()

    def close(self):
        """Close the connection to RabbitMQ."""
        self.client.close()
