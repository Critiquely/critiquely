"""CLI tool for code review using MCP server."""

import asyncio
import click
import logging

from critiquely.core.git_utils import clone_git_repo
from critiquely.core.review import run_code_review, CodeReviewError

logger = logging.getLogger(__name__)

@click.command()
@click.option(
    "--interactive",
    is_flag=True,
    help="Enable human-in-the-loop monitoring for agent tools"
)
@click.option(
    "--repo_url",
    required=True,
    help="The repository URL you want to critique"
)
@click.option(
    "--branch",
    required=True,
    help="The branch within the repository you want to critique"
)
@click.pass_context
def cli(ctx: click.Context, interactive: bool, repo_url: str, branch: str) -> None:
    """Run the code review CLI."""

    async def run():
        local_dir = clone_git_repo(repo_url, branch)
        try:
            result = await run_code_review(
                local_dir,
                remote_repo=repo_url,
                branch=branch,
                interactive=interactive
            )
            click.echo(result)
            click.echo("\n" + "=" * 50 + "\n")
        except CodeReviewError as e:
            logger.error(f"Code review failed: {e}", exc_info=True)
            click.echo(f"Code review failed: {e}", err=True)
            ctx.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    cli()