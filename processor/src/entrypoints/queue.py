"""Queue worker entrypoint for processing code review requests from RabbitMQ."""

import logging
import sys

from src.config import settings
from src.queue.consumer import ReviewQueueConsumer

logger = logging.getLogger(__name__)


def run_queue():
    consumer = ReviewQueueConsumer()

    try:
        consumer.start_consuming()
    except Exception as e:
        logger.error(f"❌ Queue worker failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        consumer.close()
