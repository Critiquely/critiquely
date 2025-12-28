"""CLI tool and queue worker for Critiquely agentic workflows."""

import asyncio
import click
import logging
import sys
from typing import Optional

from src.config import settings
from src.workflows import WorkflowRegistry

# Import workflows to trigger registration
import src.workflows  # noqa: F401

logging.basicConfig(
    format="%(asctime)s %(levelname)7s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def cli(ctx):
    """Critiquely - Agentic code review and analysis tool."""
    if ctx.invoked_subcommand is None:
        # Default to interactive mode when no subcommand given
        from src.interactive import run_interactive

        run_interactive()


@cli.command()
@click.option(
    "--workflow",
    "-w",
    type=str,
    default=None,
    help="Specific workflow to consume (default: all registered workflows)",
)
def worker(workflow: Optional[str]):
    """Run as a queue worker, processing workflow tasks from RabbitMQ."""
    from src.queue import start_queue_worker

    if workflow:
        # Validate workflow exists
        if not WorkflowRegistry.get(workflow):
            available = ", ".join(WorkflowRegistry.all_workflows().keys())
            logger.error(f"Unknown workflow: {workflow}")
            logger.info(f"Available workflows: {available}")
            sys.exit(1)

    logger.info("Starting Critiquely Queue Worker")
    if workflow:
        logger.info(f"Filtering to workflow: {workflow}")

    start_queue_worker(workflow_filter=workflow)


@cli.command()
@click.option("--repo-url", required=True, help="Repository URL to review")
@click.option("--pr-url", required=True, help="Pull request URL to review")
@click.option("--branch", required=True, help="Branch to review")
@click.option(
    "--modified-files", required=True, help="JSON list of modified files"
)
def review(repo_url: str, pr_url: str, branch: str, modified_files: str):
    """Run code review on a pull request."""
    from src.workflows.review import ReviewWorkflow

    if not settings.github_token:
        logger.error("GITHUB_TOKEN is unset or empty")
        sys.exit(1)

    async def run():
        try:
            workflow = ReviewWorkflow()
            result = await workflow.run(
                {
                    "repo_url": repo_url,
                    "original_pr_url": pr_url,
                    "branch": branch,
                    "modified_files": modified_files,
                }
            )
            click.echo(f"Review completed: {result}")
        except Exception as e:
            logger.error(f"Code review failed: {e}", exc_info=True)
            sys.exit(1)

    asyncio.run(run())


@cli.command("list-workflows")
def list_workflows():
    """List all available workflows."""
    workflows = WorkflowRegistry.all_workflows()

    if not workflows:
        click.echo("No workflows registered.")
        return

    click.echo("Available workflows:\n")
    for name, wf_class in workflows.items():
        meta = wf_class.metadata()
        click.echo(f"  {name}")
        click.echo(f"    Description: {meta.description}")
        click.echo(f"    Queue: {meta.queue_name}")
        click.echo(f"    Events: {', '.join(meta.supported_events)}")
        click.echo()


@cli.command()
def interactive():
    """Launch interactive mode with slash commands."""
    from src.interactive import run_interactive

    run_interactive()


# Backward compatibility: support old --queue-mode flag
@cli.command("legacy", hidden=True)
@click.option("--queue-mode", is_flag=True)
@click.option("--repo_url", default=None)
@click.option("--original_pr_url", default=None)
@click.option("--branch", default=None)
@click.option("--modified_files", default=None)
@click.pass_context
def legacy(
    ctx: click.Context,
    queue_mode: bool,
    repo_url: str,
    original_pr_url: str,
    branch: str,
    modified_files: str,
):
    """Legacy CLI interface (deprecated)."""
    import warnings

    warnings.warn(
        "Legacy CLI flags are deprecated. Use subcommands instead: "
        "'critiquely worker' or 'critiquely review'",
        DeprecationWarning,
    )

    if queue_mode:
        ctx.invoke(worker)
    else:
        if not all([repo_url, original_pr_url, branch, modified_files]):
            logger.error("Missing required arguments for CLI mode")
            sys.exit(1)
        ctx.invoke(
            review,
            repo_url=repo_url,
            pr_url=original_pr_url,
            branch=branch,
            modified_files=modified_files,
        )


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
