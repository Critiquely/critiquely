"""CLI tool for code review using MCP server."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import click
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langchain_mcp_adapters.client import MultiServerMCPClient
from .human_in_the_loop import add_human_in_the_loop

# Constants
DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"
AGENT_PROMPT = """You are an expert Python code reviewer and developer. Your task is to:
1. Analyze the repository code
2. Identify 5 specific improvements
3. Implement each improvement
4. Create a pull request

Follow these steps:
1. Clone the repository
2. Analyze the repository structure and identify Python files
3. For each improvement:
   - Explain the improvement
   - Implement the change
   - Include tests if applicable
4. After implementing all improvements, create a new branch and add and commit the changes.
5. Push the changes to the remote repository.
6. Create a pull request using the create_pull_request tool.
7. Once done, respond with "TASK COMPLETED: Pull request created with 5 improvements"

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
            }
        }
    )
    
    try:
        yield client
    finally:
        if hasattr(client, 'close'):
            await client.close()


async def run_code_review(interactive: bool = False) -> Dict[str, Any]:
    """Run the code review using MCP server.
    
    Args:
        interactive: Whether to enable human-in-the-loop monitoring
        
    Returns:
        Dict[str, Any]: The result of the code review
        
    Raises:
        CodeReviewError: If there's an error during the review process
    """
    try:
        async with get_mcp_client() as client:
            logger.info("Fetching tools from MCP server")
            tools = await client.get_tools()
            
            if interactive:
                wrapped_tools = []
                for tool in tools:
                    try:
                        wrapped_tool = add_human_in_the_loop(tool)
                        wrapped_tools.append(wrapped_tool)
                    except Exception as e:
                        logger.warning(f"Could not wrap tool {getattr(tool, 'name', str(tool))} with human-in-the-loop: {e}")
                        wrapped_tools.append(tool)
                tools = wrapped_tools
            
            logger.info("Creating review agent")
            checkpointer = InMemorySaver()
            agent = create_react_agent(
                model=DEFAULT_MODEL,
                tools=tools,
                prompt=AGENT_PROMPT,
                checkpointer=checkpointer
            )
            
            logger.info("Running code review")
            
            messages = [{
                "role": "user",
                "content": "Conduct a code review of the Critiquely/critiquely GitHub repository."
            }]
            config = {"configurable": {"thread_id": "1"}}
            
            input_data = {"messages": messages}
            
            while True:
                chunks = []
                async for chunk in agent.astream(input_data, config):
                    chunks.append(chunk)
                    print(chunk)
                    print("\n")
                
                last_chunk = chunks[-1] if chunks else {}
                if "__interrupt__" in last_chunk:
                    interrupt_data = last_chunk["__interrupt__"]
                    print("\nAgent is waiting for your input...")
                    print("Please respond with one of the following options:")
                    print("1. Type 'accept' to approve the action")
                    print("2. Type 'edit' to modify the action arguments")
                    print("3. Type 'respond' to send a custom response")
                    
                    user_choice = input("\nYour choice (accept/edit/respond): ").strip().lower()
                    
                    if user_choice == "accept":
                        resume_cmd = [{"type": "accept"}]
                    elif user_choice == "edit":
                        print("\nCurrent arguments:")
                        print(interrupt_data[0].value[0]["action_request"]["args"])
                        print("\nEnter new arguments as a JSON object:")
                        new_args = input("> ").strip()
                        resume_cmd = [{"type": "edit", "args": {"args": new_args}}]
                    elif user_choice == "respond":
                        print("\nEnter your response:")
                        user_response = input("> ").strip()
                        resume_cmd = [{"type": "response", "args": user_response}]
                    else:
                        print("Invalid choice. Defaulting to 'accept'.")
                        resume_cmd = [{"type": "accept"}]
                    
                    input_data = Command(resume=resume_cmd)
                else:
                    break
            
            final_state = await checkpointer.aget(config)
            return {"messages": final_state.get("messages", [])}
    except Exception as e:
        logger.error(f"Error during code review: {e}")
        raise CodeReviewError(f"Failed to complete code review: {e}") from e


@click.command()
@click.option(
    "--interactive",
    is_flag=True,
    help="Enable human-in-the-loop monitoring for agent tools"
)
@click.pass_context
def cli(ctx: click.Context, interactive: bool) -> None:
    """Run the code review CLI.
    
    Args:
        ctx: Click context
        interactive: Whether to enable human-in-the-loop monitoring
    """
    async def run() -> None:
        try:
            result = await run_code_review(interactive=interactive)
            click.echo(result)
            click.echo("\n" + "=" * 50 + "\n")
        except CodeReviewError as e:
            click.echo(f"Error: {e}", err=True)
    
    asyncio.run(run())


if __name__ == "__main__":
    cli()
