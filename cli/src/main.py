"""CLI tool for code review using MCP server."""

import asyncio
import click
import logging

from src.core.review import run_review_graph


logger = logging.getLogger(__name__)

@click.command()
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
def cli(ctx: click.Context, repo_url: str, branch: str, modified_files: str) -> None:
    """Run the code review CLI."""

    async def run():
        try:
            result = await run_review_graph(
                repo_url=repo_url,
                repo_branch=branch,
                modified_files=modified_files,
            )
            click.echo(result)
            click.echo("\n" + "=" * 50 + "\n")
        except Exception as e:
            click.echo(f"Code review failed: {e}", err=True)

    asyncio.run(run())


if __name__ == "__main__":
    cli()