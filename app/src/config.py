from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_token: str = ""
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "critiquely"
    rabbitmq_pass: str = "critiquely123"
    queue_name: str = "code_review_queue"
    
    @property
    def rabbitmq_url(self) -> str:
        """Construct RabbitMQ URL from components."""
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}@{self.rabbitmq_host}:{self.rabbitmq_port}"
    
    class Config:
        env_file = ".env"


settings = Settings()