"""RabbitMQ consumer for processing workflow requests."""

import asyncio
import json
import logging
import sys
from typing import Dict, Any, Optional, Set

from src.config import settings
from src.workflows import WorkflowRegistry
from .rabbitmq import RabbitMQClient

logger = logging.getLogger(__name__)


class WorkflowQueueConsumer:
    """Generic consumer that routes messages to appropriate workflows.

    This consumer can handle multiple workflow queues, dispatching messages
    to the correct workflow based on the queue name.
    """

    def __init__(self, workflow_filter: Optional[str] = None):
        """Initialize the consumer.

        Args:
            workflow_filter: If set, only consume from this workflow's queue.
        """
        self.client = RabbitMQClient()
        self.workflow_filter = workflow_filter
        self._queues_to_consume: Set[str] = set()

    def _setup_queues(self) -> None:
        """Setup queues based on registered workflows."""
        queue_mappings = WorkflowRegistry.get_queue_mappings()

        if self.workflow_filter:
            if self.workflow_filter not in queue_mappings:
                raise ValueError(f"Unknown workflow: {self.workflow_filter}")
            self._queues_to_consume = {queue_mappings[self.workflow_filter]}
        else:
            self._queues_to_consume = set(queue_mappings.values())

        # Declare all queues we'll consume from
        for queue_name in self._queues_to_consume:
            self.client.declare_queue(queue_name)
            logger.info(f"Declared queue: {queue_name}")

    def _get_workflow_for_queue(self, queue_name: str):
        """Get the workflow class for a given queue name."""
        return WorkflowRegistry.get_for_queue(queue_name)

    def process_message(self, ch, method, properties, body):
        """Process a message by dispatching to the appropriate workflow."""
        queue_name = method.routing_key

        try:
            message_data = json.loads(body.decode("utf-8"))
            logger.info(f"Processing message from {queue_name}")

            # Find the workflow for this queue
            workflow_cls = self._get_workflow_for_queue(queue_name)
            if not workflow_cls:
                raise ValueError(f"No workflow registered for queue: {queue_name}")

            # Instantiate and run the workflow
            workflow = workflow_cls()
            asyncio.run(workflow.run(message_data))

            # Acknowledge success
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Completed {workflow_cls.metadata().name} workflow")

        except ValueError as e:
            logger.error(f"Invalid message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start_consuming(self):
        """Start consuming from all configured queues."""
        self.client.connect()
        self._setup_queues()

        # Setup consumer for each queue
        for queue_name in self._queues_to_consume:
            self.client.setup_consumer_for_queue(
                queue_name=queue_name, message_handler=self.process_message
            )

        logger.info(f"Consuming from queues: {self._queues_to_consume}")
        self.client.start_consuming()

    def close(self):
        """Close the connection."""
        self.client.close()


# Backward compatibility alias
class ReviewQueueConsumer(WorkflowQueueConsumer):
    """Deprecated: Use WorkflowQueueConsumer instead."""

    def __init__(self):
        import warnings

        warnings.warn(
            "ReviewQueueConsumer is deprecated. Use WorkflowQueueConsumer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(workflow_filter="review")


def start_queue_worker(workflow_filter: Optional[str] = None):
    """Entry point for the queue worker.

    Args:
        workflow_filter: If set, only consume from this workflow's queue.
    """
    if not settings.github_token:
        logger.error("GITHUB_TOKEN is unset or empty")
        sys.exit(1)

    consumer = WorkflowQueueConsumer(workflow_filter=workflow_filter)

    try:
        consumer.start_consuming()
    except Exception as e:
        logger.error(f"Queue worker failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        consumer.close()