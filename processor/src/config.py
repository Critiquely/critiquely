import logging
from pydantic import field_validator, ValidationError
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Required settings
    github_token: str = ""
    
    # RabbitMQ configuration with sensible defaults
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "critiquely"
    rabbitmq_pass: str = "critiquely123"
    queue_name: str = "code_review_queue"
    
    # Optional settings
    log_level: str = "INFO"
    temp_dir: Optional[str] = None
    
    @field_validator('github_token')
    @classmethod
    def validate_github_token(cls, v: str) -> str:
        """Validate GitHub token is present for production use."""
        if not v or not v.strip():
            # Allow empty token for testing, but warn
            logger.warning("⚠️  GITHUB_TOKEN is not set. Some features may not work.")
        return v.strip() if v else ""
    
    @field_validator('rabbitmq_port')
    @classmethod
    def validate_rabbitmq_port(cls, v: int) -> int:
        """Validate RabbitMQ port is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError("RabbitMQ port must be between 1 and 65535")
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @field_validator('queue_name')
    @classmethod
    def validate_queue_name(cls, v: str) -> str:
        """Validate queue name follows RabbitMQ naming conventions."""
        if not v or not v.strip():
            raise ValueError("Queue name cannot be empty")
        
        # RabbitMQ queue name restrictions
        if len(v) > 255:
            raise ValueError("Queue name cannot exceed 255 characters")
        
        return v.strip()
    
    @property
    def rabbitmq_url(self) -> str:
        """Construct RabbitMQ URL from components."""
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}@{self.rabbitmq_host}:{self.rabbitmq_port}"
    
    def validate_runtime_requirements(self) -> None:
        """Validate runtime requirements are met."""
        issues = []
        
        if not self.github_token:
            issues.append("GITHUB_TOKEN is required for GitHub operations")
        
        if issues:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {issue}" for issue in issues)
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def create_settings() -> Settings:
    """Create and validate settings with proper error handling."""
    try:
        settings = Settings()
        logger.info("✅ Configuration loaded successfully")
        return settings
    except ValidationError as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        raise


# Global settings instance
settings = create_settings()