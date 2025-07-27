FROM python:3.13-slim

ARG GITHUB_TOKEN
ARG GITHUB_MCP_SERVER_URL
ARG RABBITMQ_URL=amqp://localhost:5672
ARG ANTHROPIC_API_KEY

ENV GITHUB_TOKEN=$GITHUB_TOKEN \
    GITHUB_MCP_SERVER_URL=$GITHUB_MCP_SERVER_URL \
    RABBITMQ_URL=$RABBITMQ_URL \
    ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy application (incl. pyproject.toml, uv.lock, and src/)
COPY app/ ./

# Install Python dependencies
RUN uv sync --locked

# Default command
CMD ["uv", "run", "critiquely", "--queue-mode"]
