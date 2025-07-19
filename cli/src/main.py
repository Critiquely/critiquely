"""CLI tool for code review using MCP server."""

import asyncio
import click
import logging
import sys

from src.config import settings
from src.core.review import run_review_graph

logging.basicConfig(
    format="%(asctime)s %(levelname)7s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--repo_url", required=True, help="The repository URL you want to critique"
)
@click.option(
    "--original_pr_url", required=True, help="The pull request URL you want to critique"
)
@click.option(
    "--branch",
    required=True,
    help="The branch within the repository you want to critique",
)
@click.option(
    "--modified_files",
    required=True,
    help="A json object consisting of the modified files",
)
@click.pass_context
def cli(
    ctx: click.Context,
    repo_url: str,
    original_pr_url: str,
    branch: str,
    modified_files: str,
) -> None:
    """Run the code review CLI."""

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
    cli()
