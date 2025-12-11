"""Queue module for RabbitMQ message processing."""

from src.queue.consumer import ReviewQueueConsumer
from src.queue.rabbitmq import RabbitMQClient

__all__ = ["ReviewQueueConsumer", "RabbitMQClient"]
