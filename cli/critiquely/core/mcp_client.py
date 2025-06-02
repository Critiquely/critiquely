import os
from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import AsyncGenerator


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
    if not (server_url := os.environ.get("GITHUB_MCP_SERVER_URL")):
        raise CodeReviewError("GITHUB_MCP_SERVER_URL environment variable is required")

    # client = MultiServerMCPClient(
    #     {
    #         "github-mcp-server": {
    #             "url": f"{server_url.rstrip('/')}/sse",
    #             "transport": "sse",
    #         }
    #     }
    # )

    client = MultiServerMCPClient(
        {
            "github-mcp-server": {
                "transport": "stdio",
                "command": "docker",
                "args": [
                    "run",
                    "-i",
                    "--rm",
                    "-e",
                    "GITHUB_PERSONAL_ACCESS_TOKEN",
                    "ghcr.io/github/github-mcp-server"
                ],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN")
                }
            },
            "mcp-server-git": {
                "transport": "stdio",
                "command": "uvx",
                "args": ["mcp-server-git"]
            },
            "filesystem": {
                "transport": "stdio",
                "command": "npx",
                "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/tmp"
                ]
            }
        }
    )
    
    try:
        yield client
    finally:
        if hasattr(client, 'close'):
            await client.close()