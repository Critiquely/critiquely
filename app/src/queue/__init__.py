"""Queue processing module for RabbitMQ integration."""

from .consumer import ReviewQueueConsumer, start_queue_worker

__all__ = ['ReviewQueueConsumer', 'start_queue_worker']