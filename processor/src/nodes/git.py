import json
import logging
import tempfile

from src.state.state import DevAgentState

from src.utils.git import create_github_https_url
from src.utils.fs import get_temp_dir
from src.utils.state import get_state_value

from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError

logger = logging.getLogger(__name__)

def clone_repo(state: DevAgentState) -> dict:
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
