"""CLI tool and queue worker for code review using MCP server."""

import asyncio
import click
import logging
import sys

from src.config import settings
from src.core.review import run_review_graph
from src.queue import start_queue_worker

def configure_logging():
    """Configure logging for the application.
    
    Sets up basic logging configuration with timestamp, level, and message.
    Adjusts specific logger levels as needed.
    """
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO,
        class_=logging.JSONFormatter
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
configure_logging()


@click.command()
@click.option(
    "--queue-mode", 
    is_flag=True, 
    help="Run in queue worker mode instead of processing a single request"
)
@click.option(
    "--repo_url", 
    help="The repository URL you want to critique (required for CLI mode)"
)
@click.option(
    "--original_pr_url", 
    help="The pull request URL you want to critique (required for CLI mode)"
)
@click.option(
    "--branch",
    help="The branch within the repository you want to critique (required for CLI mode)",
)
@click.option(
    "--modified_files",
    help="A json object consisting of the modified files (required for CLI mode)",
)
@click.pass_context
def main(
    ctx: click.Context,
    queue_mode: bool,
    repo_url: str,
    original_pr_url: str,
    branch: str,
    modified_files: str,
) -> None:
    """Critiquely - Code review tool with CLI and queue processing modes."""
    
    if queue_mode:
        logger.info("🚀 Starting Critiquely Queue Worker")
        start_queue_worker()
    else:
        validate_cli_arguments(repo_url, original_pr_url, branch, modified_files)


def validate_cli_arguments(repo_url: str, original_pr_url: str, branch: str, modified_files: str) -> None:
    """Validate required CLI mode arguments.
    
    Args:
        repo_url: The repository URL to critique
        original_pr_url: The pull request URL to critique
        branch: The branch to critique
        modified_files: JSON object of modified files
        
    Raises:
        SystemExit: If any required arguments are missing
    """
    required_args = {
        'repo_url': repo_url,
        'original_pr_url': original_pr_url,
        'branch': branch,
        'modified_files': modified_files
    }
    
    missing_args = [arg for arg, value in required_args.items() if not value]
    if missing_args:
        logger.error(f"❌ Missing required arguments for CLI mode: {', '.join(missing_args)}")
        logger.info("💡 Use --queue-mode to run as a queue worker, or provide all required CLI arguments")
        sys.exit(1)

        async def run():
            if not settings.github_token:
                logger.error("❌ GITHUB_TOKEN is unset or empty")
                sys.exit(1)

            try:
                result = await run_review_graph(
                    repo_url=repo_url,
                    original_pr_url=original_pr_url,
                    base_branch=branch,
                    modified_files=modified_files,
                )
                click.echo(result)
                click.echo("\n" + "=" * 50 + "\n")
            except Exception as e:
                logger.error(f"❌ Code review failed: {e}", exc_info=True)

        asyncio.run(run())


if __name__ == "__main__":
    main()
