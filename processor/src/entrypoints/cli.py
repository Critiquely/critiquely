"""CLI entrypoint for running single code reviews."""

import logging
import sys

import click

from src.graph.graph import run_graph

logger = logging.getLogger(__name__)


async def run_cli(repo_url, original_pr_url, branch, modified_files):
    """Run a single code review in CLI mode."""
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
