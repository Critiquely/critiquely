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
        """Validate that the GitHub token is not empty.

        Args:
            v: The GitHub token value from environment or config.

        Returns:
            The stripped token string.

        Raises:
            ValueError: If the token is empty or contains only whitespace.
        """
        if not v or not v.strip():
            raise ValueError("❌ GITHUB_TOKEN is required and cannot be empty.")
        return v.strip() if v else ""

    # -----------------------------------
    # Computed Properties & Runtime Checks
    # -----------------------------------

    @property
    def rabbitmq_url(self) -> str:
        """Construct the RabbitMQ connection URL.

        Returns:
            AMQP connection URL with credentials and host information.

        Example:
            "amqp://user:pass@localhost:5672"
        """
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}"
        )

def create_settings() -> Settings:
    """Load and validate application settings from environment variables.

    Returns:
        Settings: Validated settings instance.

    Raises:
        SystemExit: Exits with code 1 if validation fails (e.g., missing GITHUB_TOKEN).
        Exception: For unexpected configuration loading errors.

    Note:
        This function is called once at module load time to create the global
        settings singleton.
    """
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
