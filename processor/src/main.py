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


@click.command()
@click.option("--queue-mode", is_flag=True, help="Run as a queue worker.")
@click.option("--repo_url", help="Repository URL.")
@click.option("--original_pr_url", help="Pull request URL.")
@click.option("--branch", help="Branch name.")
@click.option("--modified_files", help="JSON of modified files.")
def main(queue_mode, repo_url, original_pr_url, branch, modified_files):
    """Critiquely – AI-powered code review tool."""

    # Queue worker mode bypasses CLI argument checks
    if queue_mode:
        logger.info("🚀 Starting queue worker")
        run_queue()
        return

    # Validate CLI args
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
