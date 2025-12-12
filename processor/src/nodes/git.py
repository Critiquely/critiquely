import json
import logging
import tempfile

from langchain_core.messages import HumanMessage

from src.state.state import DevAgentState

from src.utils.git import create_github_https_url
from src.utils.fs import get_temp_dir
from src.utils.state import get_state_value

from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError

logger = logging.getLogger(__name__)

def clone_repo(state: DevAgentState) -> dict:
    """Clone a Git repository to a temporary directory.

    Args:
        state: DevAgentState containing:
            - repo_url: GitHub repository URL (will be converted to HTTPS format)
            - base_branch: Branch name to clone

    Returns:
        Dictionary with state updates:
            - clone_path: Temporary directory path where repo was cloned (on success)
            - messages: List containing a HumanMessage with operation status

    Note:
        Creates a shallow clone (depth=1, single branch) for efficiency.
        On failure, returns an error message without clone_path.
    """
    repo_url = create_github_https_url(get_state_value(state, "repo_url"))
    branch = get_state_value(state, "base_branch")

    try:
        clone_path = tempfile.mkdtemp(dir=get_temp_dir())
        logger.info(f"🔄 Cloning {repo_url}@{branch} into {clone_path}")

        repo = Repo.clone_from(
            repo_url, clone_path,
            branch=branch, depth=1, single_branch=True
        )
        repo.remote().set_url(get_state_value(state, "repo_url"))

        msg = f"✅ Cloned {repo_url}@{branch} to {clone_path}"
        logger.info(msg)
        return {"clone_path": clone_path, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        msg = f"❌ Failed to clone {repo_url}@{branch}: {exc}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}
