"""CLI tool for code review using MCP server."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import click
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

# Constants
DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"
AGENT_PROMPT = """You are an expert Python code reviewer and developer. Your task is to:
1. Analyze the repository code
2. Identify 5 specific improvements
3. Implement each improvement
4. Create a pull request

Follow these steps:
1. First, analyze the repository structure and identify key files
2. For each improvement:
   - Explain the improvement
   - Implement the change
   - Include tests if applicable
3. After implementing all improvements, create a pull request
4. Once done, respond with "TASK COMPLETED: Pull request created with 5 improvements"

Be concise and focus on high-impact improvements. For each change, explain why it's beneficial."""

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CodeReviewError(Exception):
    """Base exception for code review related errors."""


@asynccontextmanager
async def get_mcp_client() -> MultiServerMCPClient:
    """Context manager for MCP client lifecycle management.
    
    Yields:
        MultiServerMCPClient: Configured MCP client
        
    Raises:
        CodeReviewError: If required environment variables are missing
    """
    if not (server_url := os.environ.get("GITHUB_MCP_SERVER_URL")):
        raise CodeReviewError("GITHUB_MCP_SERVER_URL environment variable is required")

    client = MultiServerMCPClient(
        {
            "github-mcp-server": {
                "url": f"{server_url.rstrip('/')}/sse",
                "transport": "sse",
            }
        }
    )
    
    try:
        yield client
    finally:
        if hasattr(client, 'close'):
            await client.close()


async def run_code_review() -> Dict[str, Any]:
    """Run the code review using MCP server.
    
    Returns:
        Dict[str, Any]: The result of the code review
        
    Raises:
        CodeReviewError: If there's an error during the review process
    """
    try:
        async with get_mcp_client() as client:
            logger.info("Fetching tools from MCP server")
            tools = await client.get_tools()
            
            logger.info("Creating review agent")
            agent = create_react_agent(
                model=DEFAULT_MODEL,
                tools=tools,
                prompt=AGENT_PROMPT
            )
            
            logger.info("Running code review")
            return await agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": "Get the content of the Critiquely/critiquely GitHub repository. Pick any python file and make a change to it. Return the updated file contents. If you cannot make a change, return 'No changes made to the file'. To get the file contents you need to pass the path to the file in the repository, not just the file name."
                }]
            })
    except Exception as e:
        logger.error(f"Error during code review: {e}")
        raise CodeReviewError(f"Failed to complete code review: {e}") from e


@click.command()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Run the code review CLI."""
    async def run() -> None:
        try:
            result = await run_code_review()
            click.echo(result)
            click.echo("\n" + "=" * 50 + "\n")
        except CodeReviewError as e:
            click.echo(f"Error: {e}", err=True)
    
    asyncio.run(run())


if __name__ == "__main__":
    cli()
