FROM python:3.13-slim

ARG GITHUB_TOKEN
ARG RABBITMQ_URL=amqp://localhost:5672
ARG ANTHROPIC_API_KEY

ENV GITHUB_TOKEN=$GITHUB_TOKEN \
    RABBITMQ_URL=$RABBITMQ_URL \
    ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY

WORKDIR /app

# Install curl, bash, gnupg, ca-certificates, git — then install Node.js 20
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        bash \
        gnupg \
        ca-certificates \
        git && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy the app (including pyproject.toml, uv.lock, and source files)
COPY . ./

# Install Python dependencies
RUN uv sync --locked

# Default command
CMD ["uv", "run", "critiquely", "--queue-mode"]
