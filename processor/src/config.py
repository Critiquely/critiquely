"""Critiquely processor configuration."""

import logging
from typing import Optional

import pika
from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

class Settings(BaseSettings):
    """Application settings loaded from environment or .env."""

    # GitHub
    github_token: str = ""

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "critiquely"
    rabbitmq_pass: str = "critiquely123"
    queue_name: str = "code_review_queue"

    # Application
    log_level: str = "INFO"
    temp_dir: Optional[str] = None

    # -----------------------------------
    # Field Validators
    # -----------------------------------

    @field_validator("github_token")
    @classmethod
    def validate_github_token(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("❌ GITHUB_TOKEN is required and cannot be empty.")
        return v.strip() if v else ""

    # -----------------------------------
    # Computed Properties & Runtime Checks
    # -----------------------------------

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}"
        )

def create_settings() -> Settings:
    """Load settings and emit clear startup logs."""
    try:
        s = Settings()
        return s
    except ValidationError as e:
        for err in e.errors():
            logger.error(f"  {err['msg']}")
        raise SystemExit(1)  # <-- THIS IS REQUIRED

    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        raise


# Global singleton – loaded once
settings = create_settings()
