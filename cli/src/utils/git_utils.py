"""Git utilities for working with repositories in temporary environments."""

from pathlib import Path
import tempfile
from git import Repo, GitCommandError


def clone_git_repo(repo_url: str, branch: str) -> Path:
    """
    Clone a specific branch of a Git repository into a temporary directory.

    Args:
        repo_url (str): The HTTPS or SSH URL of the remote Git repository.
        branch (str): The branch to clone from the remote repository.

    Returns:
        Path: Path to the temporary directory containing the cloned repository.

    Raises:
        GitCommandError: If the clone operation fails.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        Repo.clone_from(
            repo_url,
            temp_dir,
            branch=branch,
            depth=1,
            single_branch=True
        )
        print(f"Cloned {repo_url} (branch: {branch}) to {temp_dir}")
        return temp_dir
    except GitCommandError as exc:
        print(f"Failed to clone: {exc}")
        raise
