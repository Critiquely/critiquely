import asyncio
import logging
import sys

import click

from src.config import settings
from src.entrypoints.cli import run_cli
from src.entrypoints.queue import run_queue

logging.basicConfig(
    format="%(asctime)s %(levelname)7s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

REQUIRED_CLI_ARGS = ["repo_url", "original_pr_url", "branch", "modified_files"]

async def run_cli(repo_url, original_pr_url, branch, modified_files):
    """Run a single code review in CLI mode.

    Args:
        repo_url: GitHub repository URL to review.
        original_pr_url: URL of the pull request being reviewed.
        branch: Name of the branch to checkout and review.
        modified_files: JSON string containing the list of modified files.

    Raises:
        SystemExit: Exits with code 1 if the review fails.

    Note:
        This function runs the LangGraph workflow once and exits.
        Errors are logged with full traceback before exiting.
    """
    try:
        result = await run_graph(
            repo_url=repo_url,
            original_pr_url=original_pr_url,
            base_branch=branch,
            modified_files=modified_files,
        )
        click.echo(result)

    except Exception as exc:
        logger.error(f"❌ Review failed: {exc}", exc_info=True)
        sys.exit(1)

def run_queue():
    """Run the code review processor in queue consumer mode.

    Starts a ReviewQueueConsumer that listens for review requests from
    a message queue and processes them asynchronously.

    Raises:
        SystemExit: Exits with code 1 if the queue worker fails.

    Note:
        This runs indefinitely until interrupted or an error occurs.
        The consumer connection is properly closed in the finally block.
    """
    consumer = ReviewQueueConsumer()

    try:
        consumer.start_consuming()
    except Exception as e:
        logger.error(f"❌ Queue worker failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        consumer.close()


@click.command()
@click.option("--queue-mode", is_flag=True, help="Run as a queue worker.")
@click.option("--repo_url", help="Repository URL.")
@click.option("--original_pr_url", help="Pull request URL.")
@click.option("--branch", help="Branch name.")
@click.option("--modified_files", help="JSON of modified files.")
def main(queue_mode, repo_url, original_pr_url, branch, modified_files):
    """Critiquely – AI-powered code review tool."""

    # Queue Mode
    if queue_mode:
        logger.info("🚀 Starting queue worker")
        run_queue()
        return

    # CLI Mode
    args = locals()
    missing = [arg for arg in REQUIRED_CLI_ARGS if not args[arg]]
    if missing:
        logger.error(f"❌ Missing: {', '.join(missing)}")
        sys.exit(1)
        
    asyncio.run(
        run_cli(repo_url, original_pr_url, branch, modified_files)
    )

if __name__ == "__main__":
    main()
