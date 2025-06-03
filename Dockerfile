FROM python:3.13-slim

ARG GITHUB_TOKEN
ARG GITHUB_MCP_SERVER_URL

WORKDIR /app

ENV GITHUB_TOKEN=${GITHUB_TOKEN}
ENV GITHUB_MCP_SERVER_URL=${GITHUB_MCP_SERVER_URL}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY cli/ /app/cli/

RUN pip install --no-cache-dir -e /app/cli

WORKDIR /app/cli

CMD ["critiquely"]
