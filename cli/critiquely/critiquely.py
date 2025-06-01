"""CLI tool for code review using MCP server."""
import tempfile
from pathlib import Path
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from git import Repo, GitCommandError, InvalidGitRepositoryError

import click
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import tool, ToolException
from .human_in_the_loop import add_human_in_the_loop

# Constants
DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"
AGENT_PROMPT = """
You are an expert Python engineer and code reviewer. Your task is to review the cloned Git repository, make **one** meaningful improvement, and submit it via a pull request.

## Workflow

1. Use `list_directory` and `read_file` to explore the codebase. Focus on files most likely to benefit from improvements.
2. Identify a single, high-impact improvement. Once selected, proceed to the next steps—**do not make multiple changes**.
3. Use `git_create_branch` to create a new branch named like: `code_review_improvement_<random_number>`.
4. Implement your improvement:
   - Clearly explain the motivation and benefits.
   - Modify the relevant code using `edit_file` or `write_file. When calling edit_file, you must include a list of edits under the edits key. Each edit should have type, old, and new fields. When calling edit_file, edits must be a proper array — do not pass it as a stringified JSON object.
   - Add tests or documentation updates if appropriate.
5. Stage and push the change using `git_add`, `git_commit`, and `local_git_push`.
6. After pushing your change, create a pull request.
7. Once complete, return exactly the following output:
    ```
    TASK COMPLETED: Pull request created with 1 improvement
    ```

## Requirements

- Make **only one** improvement. No more, no less.
- Follow PEP 8 and include type hints where helpful.
- Avoid unrelated or “drive-by” refactors.
- Keep commit messages and explanations concise and relevant.
- Do **not** create a pull request until after the commit has been pushed.
"""

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

@tool
def local_git_push(repo_path: str, branch: str) -> str:
    """
    Pushes the specified branch to the remote origin using GitPython.

    Args:
        repo_path: Path to the local Git repository.
        branch: Name of the branch to push.

    Returns:
        A confirmation message if successful.

    Raises:
        ToolException if the push fails.
    """
    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        raise ToolException(f"{repo_path} is not a valid Git repository")

    try:
        origin = repo.remote(name="origin")
        push_result = origin.push(refspec=branch)

        for res in push_result:
            if res.flags & res.ERROR:
                raise ToolException(f"Git push failed: {res.summary}")
        
        return f"Push successful: {res.summary}"

    except GitCommandError as e:
        raise ToolException(f"Git push failed: {e.stderr or str(e)}")
    
def clone_git_repo(repo_url: str, branch: str) -> Path:
    """
    Clone a specific branch of a git repository to a temporary directory.

    Args:
        repo_url (str): The HTTPS or SSH URL of the GitHub repository.
        branch (str): The branch to clone.

    Returns:
        Path: Path to the temporary directory containing the cloned repository.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        Repo.clone_from(
            repo_url,
            temp_dir,
            branch=branch,
            depth=1,
            single_branch=True
        )
        print(f"Cloned {repo_url} (branch: {branch}) to {temp_dir}")
        return temp_dir
    except GitCommandError as exc:
        print(f"Failed to clone: {exc}")
        raise

async def run_code_review(local_dir, remote_repo, branch, interactive: bool = False, ) -> Dict[str, Any]:
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
            mcp_tools = await client.get_tools()
            local_tools = [ local_git_push ]
            tools = mcp_tools + local_tools
            
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
                "content": (
                    f"Conduct a code review of the repository cloned to: {local_dir}.\n"
                    f"The remote URL of the repository is: {remote_repo}.\n"
                    f"The branch we have pulled is: {branch}.\n"
                )
            }]
            config = {
                "configurable": {
                    "thread_id": "1", 
                }
            }
            
            input_data = {
                "messages": messages,
            }
            
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

def clone_git_repo(repo_url: str, branch: str) -> Path:
    """
    Clone a specific branch of a git repository to a temporary directory.

    Args:
        repo_url (str): The HTTPS or SSH URL of the GitHub repository.
        branch (str): The branch to clone.

    Returns:
        Path: Path to the temporary directory containing the cloned repository.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        Repo.clone_from(
            repo_url,
            temp_dir,
            branch=branch,
            depth=1,
            single_branch=True
        )
        print(f"Cloned {repo_url} (branch: {branch}) to {temp_dir}")
        return temp_dir
    except GitCommandError as exc:
        print(f"Failed to clone: {exc}")
        raise

@click.command()
@click.option(
    "--interactive",
    is_flag=True,
    help="Enable human-in-the-loop monitoring for agent tools"
)
@click.option(
    "--repo_url",
    help="The repository URL you want to critique"
)
@click.option(
    "--branch",
    help="The branch within the repository you want to critique"
)
@click.pass_context
def cli(ctx: click.Context, interactive: bool, repo_url: str, branch: str) -> None:
    """Run the code review CLI.
    
    Args:
        ctx: Click context
        interactive: Whether to enable human-in-the-loop monitoring
        repo_url: Repository to critique
        branch: Branch to critique
    """
    async def run() -> None:

        locla_dir = clone_git_repo(repo_url, branch)
        try:
            result = await run_code_review(locla_dir, repo_url, branch, interactive=interactive)
            click.echo(result)
            click.echo("\n" + "=" * 50 + "\n")
        except CodeReviewError as e:
            click.echo(f"Error: {e}", err=True)
    
    asyncio.run(run())


if __name__ == "__main__":
    cli()
