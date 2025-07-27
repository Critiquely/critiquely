from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import AsyncGenerator
from src.config import settings
from src.utils.fs import get_temp_dir


class CodeReviewError(Exception):
    """Raised when there is a critical failure during MCP client setup."""


@asynccontextmanager
async def get_mcp_client() -> AsyncGenerator[MultiServerMCPClient, None]:
    """Context manager for MCP client lifecycle management.

    Yields:
        MultiServerMCPClient: Configured MCP client

    Raises:
        CodeReviewError: If required environment variables are missing
    """
    client = MultiServerMCPClient(
        {
            # Temporarily commented out until Docker-in-Docker is properly configured
            # "github-mcp-server": {
            #     "transport": "stdio",
            #     "command": "docker",
            #     "args": [
            #         "run",
            #         "-i",
            #         "--rm",
            #         "-e",
            #         "GITHUB_PERSONAL_ACCESS_TOKEN",
            #         "ghcr.io/github/github-mcp-server",
            #     ],
            #     "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_token},
            # },
            # Temporarily commented out until proper MCP server setup
            # "mcp-server-git": {
            #     "transport": "stdio",
            #     "command": "uvx",
            #     "args": ["mcp-server-git"],
            # },
            # "filesystem": {
            #     "transport": "stdio",
            #     "command": "npx",
            #     "args": [
            #         "-y",
            #         "@modelcontextprotocol/server-filesystem",
            #         get_temp_dir(),
            #     ],
            # },
        }
    )

    try:
        yield client
    finally:
        if hasattr(client, "close"):
            await client.close()
