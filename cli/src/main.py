"""CLI tool for code review using MCP server."""

import asyncio
import click
import logging

from src.core.git_utils import clone_git_repo
from src.core.review import run_code_review, CodeReviewError

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
@click.option(
    "--modified_files",
    required=True,
    help="A json object consisting of the modified files"
)
@click.pass_context
def cli(ctx: click.Context, interactive: bool, repo_url: str, branch: str, modified_files: str) -> None:
    """Run the code review CLI."""

    async def run():
        local_dir = clone_git_repo(repo_url, branch)
        try:
            result = await run_code_review(
                local_dir,
                remote_repo=repo_url,
                branch=branch,
                modified_files=modified_files,
                interactive=interactive
            )
            click.echo(result)
            click.echo("\n" + "=" * 50 + "\n")
        except CodeReviewError as e:
            click.echo(f"Code review failed: {e}", err=True)

    asyncio.run(run())


if __name__ == "__main__":
    cli()