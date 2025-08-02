"""CLI tool for code review using MCP server."""

from pathlib import Path
from contextlib import asynccontextmanager

from git import Repo, GitCommandError, InvalidGitRepositoryError

from langchain_core.tools import tool, ToolException


@tool
def local_git_push(path: str, branch: str) -> str:
    """
    Pushes the specified branch to the remote origin using GitPython.

    Args:
        path: Path to the local Git repository.
        branch: Name of the branch to push.

    Returns:
        A confirmation message if successful.

    Raises:
        ToolException if the push fails.
    """
    try:
        repo = Repo(path)
    except InvalidGitRepositoryError:
        raise ToolException(f"{path} is not a valid Git repository")

    try:
        origin = repo.remote(name="origin")
        push_result = origin.push(refspec=branch)

        for res in push_result:
            if res.flags & res.ERROR:
                raise ToolException(f"Git push failed: {res.summary}")

        return f"Push successful: {res.summary}"

    except GitCommandError as e:
        raise ToolException(f"Git push failed: {e.stderr or str(e)}")
