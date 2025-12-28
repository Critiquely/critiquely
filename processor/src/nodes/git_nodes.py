"""Shared Git and GitHub nodes for Critiquely workflows.

These nodes handle common Git operations like cloning, branching,
committing, pushing, and creating pull requests. They can be reused
across different workflow types.
"""

import logging
import tempfile
from urllib.parse import urlparse
from uuid import uuid4

from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError
from github import Auth, Github
from github.GithubException import GithubException
from langchain_core.messages import HumanMessage

from src.config import settings
from src.utils.fs import get_temp_dir
from src.utils.git import create_github_https_url
from src.utils.state import get_state_value

logger = logging.getLogger(__name__)


class GitOperationError(Exception):
    """Custom exception for Git operations."""

    pass


def clone_repo(state: dict) -> dict:
    """Clone a repository at a specific branch.

    Args:
        state: Workflow state containing repo_url and base_branch.

    Returns:
        Updated state with clone_path.
    """
    repo_url = get_state_value(state, "repo_url")
    branch = get_state_value(state, "base_branch")

    git_url = create_github_https_url(repo_url)

    try:
        temp_dir = tempfile.mkdtemp(dir=get_temp_dir())
        logger.info(f"Cloning {repo_url}@{branch} into {temp_dir}")
        repo = Repo.clone_from(
            git_url, temp_dir, branch=branch, depth=1, single_branch=True
        )
        # Scrub token from remote config
        repo.remote().set_url(repo_url)

        msg = f"Cloned {repo_url}@{branch} to {temp_dir}"
        logger.info(msg)
        return {"clone_path": temp_dir, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"Failed to clone {repo_url}@{branch}: {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


def create_branch(state: dict) -> dict:
    """Create and checkout a new branch for changes.

    Args:
        state: Workflow state containing clone_path and base_branch.

    Returns:
        Updated state with new_branch name.
    """
    clone_path = get_state_value(state, "clone_path")
    branch = get_state_value(state, "base_branch")

    try:
        repo = Repo(clone_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"Cannot open repo at '{clone_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    branch_name = f"critiquely/{branch}-improvements-{uuid4().hex[:8]}"
    try:
        logger.info(f"Creating a new branch: {branch_name}")
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        msg = f"New branch created: {branch_name}"
        logger.info(msg)
        return {
            "new_branch": branch_name,
            "messages": [HumanMessage(content=msg)],
        }

    except GitCommandError as exc:
        error = f"Failed to create {branch_name}: {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


def commit_code(state: dict) -> dict:
    """Stage and commit all changes.

    Args:
        state: Workflow state containing clone_path, new_branch,
               repo_url, and current_recommendation.

    Returns:
        Updated state with commit message.
    """
    clone_path = get_state_value(state, "clone_path")
    branch = get_state_value(state, "new_branch")
    repo_url = get_state_value(state, "repo_url")
    current_recommendation = get_state_value(state, "current_recommendation")

    git_url = create_github_https_url(repo_url)
    recommendation_summary = current_recommendation.get("summary", "Apply changes")

    try:
        repo = Repo(clone_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"Cannot open repo at '{clone_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Inject token into the origin URL
    origin = repo.remote(name="origin")
    origin.set_url(git_url)

    # Stage & commit
    try:
        repo.git.add("--all")
        repo.index.commit(recommendation_summary)
        msg = f"Committed changes to '{branch}'"
        logger.info(msg)
        return {"messages": [HumanMessage(content=msg)]}
    except GitCommandError as exc:
        msg = f"Failed to add/commit changes: {exc}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}


def push_code(state: dict) -> dict:
    """Push the current branch to the remote.

    Args:
        state: Workflow state containing clone_path, new_branch, and repo_url.

    Returns:
        Updated state confirming push.
    """
    clone_path = get_state_value(state, "clone_path")
    branch = get_state_value(state, "new_branch")
    repo_url = get_state_value(state, "repo_url")

    git_url = create_github_https_url(repo_url)

    try:
        repo = Repo(clone_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"Cannot open repo at '{clone_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Inject token into the origin URL
    origin = repo.remote(name="origin")
    origin.set_url(git_url)

    try:
        logger.info(f"Pushing branch '{branch}' to origin")
        origin.push(refspec=f"{branch}:{branch}")
        msg = f"Pushed branch '{branch}' to origin"
        logger.info(msg)
        return {"new_branch": branch, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"Failed to push to '{branch}': {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


def pr_repo(state: dict) -> dict:
    """Create a pull request on GitHub.

    Args:
        state: Workflow state containing repo_url, base_branch, and new_branch.

    Returns:
        Updated state with pr_number and pr_url.
    """
    repo_url = get_state_value(state, "repo_url")
    base_branch = get_state_value(state, "base_branch")
    head_branch = get_state_value(state, "new_branch")

    title = "Critiquely improvements"
    body = "Automated code review fixes and improvements."

    if not settings.github_token:
        msg = "GITHUB_TOKEN is unset or empty."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    repo_name = urlparse(repo_url).path.lstrip("/").removesuffix(".git")

    try:
        gh = Github(auth=Auth.Token(settings.github_token))
        repo = gh.get_repo(repo_name)
    except GithubException as exc:
        msg = f"Failed to access repo '{repo_name}': {exc.data.get('message', exc)}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    try:
        pr = repo.create_pull(
            base=base_branch,
            head=head_branch,
            title=title,
            body=body,
            draft=False,
        )
        msg = f"Opened PR #{pr.number}: {pr.html_url}"
        logger.info(msg)
        return {
            "pr_number": pr.number,
            "pr_url": pr.html_url,
            "messages": [HumanMessage(content=msg)],
        }

    except GithubException as exc:
        msg = (
            f"Failed to open PR {head_branch} → {base_branch}: "
            f"{exc.data.get('message', exc)}"
        )
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}


def comment_on_original_pr(state: dict) -> dict:
    """Comment on the original PR that triggered the review.

    Args:
        state: Workflow state containing original_pr_url and pr_url.

    Returns:
        Updated state confirming comment was posted.
    """
    original_pr_url = state.get("original_pr_url")

    if not settings.github_token:
        msg = "GITHUB_TOKEN is unset or empty."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Parse original PR URL to extract repo and PR number
    try:
        # Expected format: https://github.com/owner/repo/pull/123
        url_parts = original_pr_url.rstrip("/").split("/")
        if len(url_parts) < 7 or url_parts[-2] != "pull":
            raise ValueError("Invalid PR URL format")

        repo_name = f"{url_parts[-4]}/{url_parts[-3]}"
        pr_number = int(url_parts[-1])
    except (ValueError, IndexError) as e:
        msg = f"Failed to parse PR URL '{original_pr_url}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    try:
        gh = Github(auth=Auth.Token(settings.github_token))
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
    except Exception as exc:
        msg = f"Failed to access PR #{pr_number} in '{repo_name}': {exc}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    comment_body = (
        f"**Critiquely Review Complete**\n\n"
        f"**Review PR:** {state.get('pr_url')}\n\n"
        f"The improvements include automated code review fixes and enhancements. "
        f"Please review the changes and merge if they look good!"
    )

    try:
        pr.create_issue_comment(comment_body)
        msg = f"Commented on original PR {original_pr_url}"
        logger.info(msg)
        return {
            "original_pr_url": original_pr_url,
            "messages": [HumanMessage(content=msg)],
        }

    except Exception as exc:
        msg = f"Failed to comment on PR {original_pr_url}: {exc}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}
