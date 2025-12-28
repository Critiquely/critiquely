"""Interactive CLI mode for Critiquely."""

import asyncio
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import settings
from src.workflows import WorkflowRegistry

logger = logging.getLogger(__name__)

# Disable logging noise in interactive mode
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BANNER = r"""
[bold cyan]
   ___      _ _   _                  _
  / __\ __ (_) |_(_) __ _ _   _  ___| |_   _
 / / | '__| | __| |/ _` | | | |/ _ \ | | | |
/ /__| |  | | |_| | (_| | |_| |  __/ | |_| |
\____/_|  |_|\__|_|\__, |\__,_|\___|_|\__, |
                      |_|             |___/
[/bold cyan]
[dim]AI-Powered Code Review & Analysis[/dim]
"""

HELP_TEXT = """
## Available Commands

| Command | Description |
|---------|-------------|
| `/review --pr <url>` | Run code review on a PR |
| `/workflows` | List available workflows |
| `/status` | Show current repo context |
| `/help` | Show this help message |
| `/exit` | Exit the CLI |

## Usage Examples

```
/review --pr https://github.com/owner/repo/pull/123
/review  # prompts for PR URL
```

The review command will automatically:
- Fetch PR details (title, branch) from GitHub
- Detect modified files and changed lines
- Generate improvement recommendations
- Create a new PR with the suggested changes

Type any command to get started!
"""


@dataclass
class RepoContext:
    """Context about the current git repository."""

    path: Optional[Path] = None
    remote_url: Optional[str] = None
    current_branch: Optional[str] = None
    is_git_repo: bool = False

    @classmethod
    def detect(cls) -> "RepoContext":
        """Detect git repository context from current directory."""
        ctx = cls()

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return ctx

            ctx.is_git_repo = True

            # Get repo root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                ctx.path = Path(result.stdout.strip())

            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                ctx.remote_url = result.stdout.strip()

            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                ctx.current_branch = result.stdout.strip()

        except Exception as e:
            logger.debug(f"Failed to detect git context: {e}")

        return ctx


class SlashCommandCompleter(Completer):
    """Completer for slash commands."""

    def __init__(self, commands: List[str]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            word = text[1:]  # Remove the slash
            for cmd in self.commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))


@dataclass
class CommandResult:
    """Result from executing a command."""

    success: bool
    message: str = ""
    should_exit: bool = False


class InteractiveCLI:
    """Interactive CLI for Critiquely."""

    def __init__(self):
        self.console = Console()
        self.repo_context = RepoContext.detect()
        self.commands: Dict[str, Callable] = {
            "review": self.cmd_review,
            "workflows": self.cmd_workflows,
            "status": self.cmd_status,
            "help": self.cmd_help,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
        }

        # Setup prompt with history
        history_file = Path.home() / ".critiquely_history"
        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=SlashCommandCompleter(list(self.commands.keys())),
            style=Style.from_dict(
                {
                    "prompt": "cyan bold",
                }
            ),
        )

    def show_banner(self):
        """Display the startup banner."""
        self.console.print(BANNER)
        self.console.print()

        # Show repo context if available
        if self.repo_context.is_git_repo:
            ctx_text = Text()
            ctx_text.append("  Repository: ", style="dim")
            ctx_text.append(str(self.repo_context.path), style="green")
            ctx_text.append("\n  Branch: ", style="dim")
            ctx_text.append(self.repo_context.current_branch or "unknown", style="yellow")
            self.console.print(
                Panel(ctx_text, title="[bold]Detected Context[/bold]", border_style="dim")
            )
        else:
            self.console.print(
                "[dim]  Not in a git repository. Use full URLs for commands.[/dim]"
            )

        self.console.print()
        self.console.print("[dim]Type /help for available commands[/dim]")
        self.console.print()

    def parse_command(self, input_text: str) -> tuple[str, Dict[str, Any]]:
        """Parse a slash command and its arguments."""
        parts = input_text.strip().split()
        if not parts:
            return "", {}

        cmd = parts[0].lstrip("/").lower()
        args = {}

        # Parse --key value pairs
        i = 1
        while i < len(parts):
            if parts[i].startswith("--"):
                key = parts[i][2:].replace("-", "_")
                if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                    args[key] = parts[i + 1]
                    i += 2
                else:
                    args[key] = True
                    i += 1
            else:
                # Positional argument
                if "positional" not in args:
                    args["positional"] = []
                args["positional"].append(parts[i])
                i += 1

        return cmd, args

    async def prompt_for_value(self, prompt_text: str, default: str = "") -> str:
        """Prompt user for a value."""
        default_hint = f" [{default}]" if default else ""
        try:
            value = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.session.prompt(f"  {prompt_text}{default_hint}: "),
            )
            return value.strip() or default
        except (EOFError, KeyboardInterrupt):
            return default

    async def cmd_review(self, args: Dict[str, Any]) -> CommandResult:
        """Run the code review workflow."""
        from src.utils.github import get_pr_modified_files, get_pr_info, parse_pr_url
        from src.workflows.review import ReviewWorkflow

        # Check for GitHub token first
        if not settings.github_token:
            return CommandResult(False, "GITHUB_TOKEN environment variable is not set")

        # Get PR URL
        pr_url = args.get("pr") or args.get("pr_url")
        if not pr_url:
            pr_url = await self.prompt_for_value("PR URL")
            if not pr_url:
                return CommandResult(False, "PR URL is required")

        # Parse PR URL to extract repo info
        try:
            owner, repo, pr_number = parse_pr_url(pr_url)
            repo_url = f"https://github.com/{owner}/{repo}.git"
        except ValueError as e:
            return CommandResult(False, str(e))

        # Fetch PR info from GitHub
        self.console.print()
        with self.console.status("[bold cyan]Fetching PR information...[/bold cyan]"):
            try:
                pr_info = await get_pr_info(pr_url)
                modified_files = await get_pr_modified_files(pr_url)
            except Exception as e:
                return CommandResult(False, f"Failed to fetch PR info: {e}")

        # Use the PR's head branch
        branch = pr_info.get("head_branch", "main")

        # Show what we found
        self.console.print(
            Panel(
                f"[bold]Repository:[/bold] {repo_url}\n"
                f"[bold]PR:[/bold] #{pr_number} - {pr_info.get('title', 'N/A')}\n"
                f"[bold]Branch:[/bold] {branch}\n"
                f"[bold]Modified Files:[/bold] {len(modified_files)}",
                title="[bold cyan]PR Details[/bold cyan]",
                border_style="cyan",
            )
        )

        # Show modified files
        if modified_files:
            file_list = "\n".join(
                f"  • {f['filename']} ({len(f.get('lines_changed', []))} lines)"
                for f in modified_files[:10]  # Show first 10
            )
            if len(modified_files) > 10:
                file_list += f"\n  ... and {len(modified_files) - 10} more"
            self.console.print(f"\n[dim]{file_list}[/dim]\n")
        else:
            self.console.print("\n[yellow]No modified files found in PR.[/yellow]\n")
            return CommandResult(False, "No files to review")

        # Run the workflow
        try:
            with self.console.status("[bold green]Running code review...[/bold green]"):
                workflow = ReviewWorkflow()
                result = await workflow.run(
                    {
                        "repo_url": repo_url,
                        "original_pr_url": pr_url,
                        "branch": branch,
                        "modified_files": modified_files,
                    }
                )

            self.console.print()
            pr_url = result.get("pr_url")
            pr_number = result.get("pr_number")
            if pr_url:
                self.console.print(
                    Panel(
                        f"[bold green]Review completed![/bold green]\n\n"
                        f"Created PR #{pr_number}: {pr_url}",
                        title="[bold]Result[/bold]",
                        border_style="green",
                    )
                )
            else:
                self.console.print(
                    Panel(
                        "[yellow]Review completed but no PR was created.[/yellow]\n\n"
                        "This may happen if there were no recommendations or changes.",
                        title="[bold]Result[/bold]",
                        border_style="yellow",
                    )
                )
            return CommandResult(True)

        except Exception as e:
            logger.exception("Review failed")
            return CommandResult(False, f"Review failed: {e}")

    async def cmd_workflows(self, args: Dict[str, Any]) -> CommandResult:
        """List available workflows."""
        workflows = WorkflowRegistry.all_workflows()

        if not workflows:
            self.console.print("[yellow]No workflows registered.[/yellow]")
            return CommandResult(True)

        table = Table(title="Available Workflows", border_style="cyan")
        table.add_column("Name", style="cyan bold")
        table.add_column("Description")
        table.add_column("Queue")
        table.add_column("Events")

        for name, wf_class in workflows.items():
            meta = wf_class.metadata()
            table.add_row(
                f"/{name}",
                meta.description,
                meta.queue_name,
                ", ".join(meta.supported_events),
            )

        self.console.print(table)
        return CommandResult(True)

    async def cmd_status(self, args: Dict[str, Any]) -> CommandResult:
        """Show current repository context."""
        if not self.repo_context.is_git_repo:
            self.console.print("[yellow]Not in a git repository.[/yellow]")
            return CommandResult(True)

        table = Table(title="Repository Context", border_style="cyan")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Path", str(self.repo_context.path))
        table.add_row("Remote", self.repo_context.remote_url or "N/A")
        table.add_row("Branch", self.repo_context.current_branch or "N/A")
        table.add_row(
            "GitHub Token",
            "[green]Set[/green]" if settings.github_token else "[red]Not set[/red]",
        )

        self.console.print(table)
        return CommandResult(True)

    async def cmd_help(self, args: Dict[str, Any]) -> CommandResult:
        """Show help message."""
        self.console.print(Markdown(HELP_TEXT))
        return CommandResult(True)

    async def cmd_exit(self, args: Dict[str, Any]) -> CommandResult:
        """Exit the CLI."""
        self.console.print("[dim]Goodbye![/dim]")
        return CommandResult(True, should_exit=True)

    async def handle_input(self, input_text: str) -> CommandResult:
        """Handle user input."""
        input_text = input_text.strip()

        if not input_text:
            return CommandResult(True)

        if not input_text.startswith("/"):
            self.console.print(
                "[yellow]Commands must start with /. Type /help for available commands.[/yellow]"
            )
            return CommandResult(True)

        cmd, args = self.parse_command(input_text)

        if cmd not in self.commands:
            self.console.print(f"[red]Unknown command: /{cmd}[/red]")
            self.console.print("[dim]Type /help for available commands[/dim]")
            return CommandResult(False)

        return await self.commands[cmd](args)

    async def run(self):
        """Run the interactive CLI loop."""
        self.show_banner()

        while True:
            try:
                # Get input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session.prompt(
                        [("class:prompt", "critiquely> ")],
                    ),
                )

                # Handle command
                result = await self.handle_input(user_input)

                if result.should_exit:
                    break

                if not result.success and result.message:
                    self.console.print(f"[red]{result.message}[/red]")

            except KeyboardInterrupt:
                self.console.print("\n[dim]Use /exit to quit[/dim]")
                continue
            except EOFError:
                break

        self.console.print()


def run_interactive():
    """Entry point for interactive mode."""
    cli = InteractiveCLI()
    asyncio.run(cli.run())
