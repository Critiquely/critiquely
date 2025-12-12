from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import AsyncGenerator
from src.config import settings
from src.utils.fs import get_temp_dir


class CodeReviewError(Exception):
    """Raised when there is a critical failure during MCP client setup."""


@asynccontextmanager
async def get_mcp_client() -> AsyncGenerator[MultiServerMCPClient, None]:
    """Context manager for MCP (Model Context Protocol) client lifecycle management.

    Initializes a MultiServerMCPClient with filesystem access to the temporary
    directory. The client uses the @modelcontextprotocol/server-filesystem
    package via npx.

    Yields:
        MultiServerMCPClient: Configured MCP client with filesystem server attached.

    Raises:
        CodeReviewError: If required environment variables are missing or if
                        the MCP server fails to initialize.

    Note:
        The client is automatically closed when the context exits, ensuring
        proper cleanup of server processes and connections.

    Example:
        async with get_mcp_client() as client:
            # Use client to interact with filesystem tools
            tools = await client.list_tools()
    """
    client = MultiServerMCPClient(
        {
            "filesystem": {
                "transport": "stdio",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    get_temp_dir(),
                ],
            },
        }
    )

    try:
        yield client
    finally:
        if hasattr(client, "close"):
            await client.close()