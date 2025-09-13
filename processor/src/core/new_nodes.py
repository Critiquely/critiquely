import logging
import tempfile
from urllib.parse import urlparse
from uuid import uuid4

from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError
from github import Auth, Github
from github.GithubException import GithubException
from langchain_core.messages import HumanMessage

from src.config import settings
from src.core.state import DevAgentState
from src.utils.fs import get_temp_dir
from src.utils.git import create_github_https_url
from src.utils.state import get_state_value

logger = logging.getLogger(__name__)

def clone_repo(state: DevAgentState) -> dict:
    repo_url = get_state_value(state, "repo_url")
    branch = get_state_value(state, "base_branch")
    git_url = create_github_https_url(repo_url)

    try:
        temp_dir = tempfile.mkdtemp(dir=get_temp_dir())
        Repo.clone_from(git_url, temp_dir, branch=branch, depth=1, single_branch=True).remote().set_url(repo_url)
        return {"clone_path": temp_dir, "messages": [HumanMessage(content=f"✅ Cloned {branch} to {temp_dir}")]}
    except GitCommandError as e:
        return {"messages": [HumanMessage(content=f"❌ Clone failed: {e}")]}
    

def create_branch(state: DevAgentState) -> dict:
    clone_path = get_state_value(state, "clone_path")
    branch = f"critiquely/{get_state_value(state, 'base_branch')}-improvements-{uuid4().hex[:8]}"

    try:
        repo = Repo(clone_path)
        repo.create_head(branch).checkout()
        return {"new_branch": branch, "messages": [HumanMessage(content=f"✅ Branch created: {branch}")]}
    except (NoSuchPathError, InvalidGitRepositoryError, GitCommandError) as e:
        return {"messages": [HumanMessage(content=f"❌ Branch creation failed: {e}")]}
    

def commit_code(state: DevAgentState) -> dict:
    clone_path = get_state_value(state, "clone_path")
    branch = get_state_value(state, "new_branch")
    repo_url = get_state_value(state, "repo_url")
    files_summary = f"Updated {len(state.get('updated_files', []))} files" if state.get("updated_files") else "Code updates"

    try:
        repo = Repo(clone_path)
        repo.remote("origin").set_url(create_github_https_url(repo_url))
        repo.git.add("--all")
        repo.index.commit(files_summary)
        return {"messages": [HumanMessage(content=f"📝 Committed changes to {branch}")]}
    except (NoSuchPathError, InvalidGitRepositoryError, GitCommandError) as e:
        return {"messages": [HumanMessage(content=f"❌ Commit failed: {e}")]}
    

def push_code(state: DevAgentState) -> dict:
    clone_path = get_state_value(state, "clone_path")
    branch = get_state_value(state, "new_branch")
    repo_url = get_state_value(state, "repo_url")

    try:
        repo = Repo(clone_path)
        origin = repo.remote("origin")
        origin.set_url(create_github_https_url(repo_url))
        origin.push(refspec=f"{branch}:{branch}")
        return {"new_branch": branch, "messages": [HumanMessage(content=f"✅ Pushed {branch}")]}
    except (NoSuchPathError, InvalidGitRepositoryError, GitCommandError) as e:
        return {"messages": [HumanMessage(content=f"❌ Push failed: {e}")]}
    

def pr_repo(state: DevAgentState) -> dict:
    repo_url = get_state_value(state, "repo_url")
    base = get_state_value(state, "base_branch")
    head = get_state_value(state, "new_branch")

    if not settings.github_token:
        return {"messages": [HumanMessage(content="❌ Missing GITHUB_TOKEN")]}

    repo_name = urlparse(repo_url).path.lstrip("/").removesuffix(".git")
    try:
        gh = Github(auth=Auth.Token(settings.github_token))
        repo = gh.get_repo(repo_name)
        pr = repo.create_pull(base=base, head=head, title="Critiquely improvements", body="Automated fixes.")
        return {"pr_number": pr.number, "pr_url": pr.html_url, "messages": [HumanMessage(content=f"✅ PR opened: {pr.html_url}")]}
    except GithubException as e:
        return {"messages": [HumanMessage(content=f"❌ PR failed: {e.data.get('message', e)}")]}
    

def comment_on_original_pr(state: DevAgentState) -> dict:
    pr_url = state.get("original_pr_url")
    if not pr_url:
        return {"messages": [HumanMessage(content="❌ Missing original PR URL")]}

    try:
        parts = pr_url.rstrip("/").split("/")
        repo_name, pr_number = f"{parts[-4]}/{parts[-3]}", int(parts[-1])
        gh = Github(auth=Auth.Token(settings.github_token))
        pr = gh.get_repo(repo_name).get_pull(pr_number)
        pr.create_issue_comment(
            f"🤖 Critiquely review done.\n\n**Review PR:** {state.get('pr_url')}\n\nAutomated fixes applied."
        )
        return {"original_pr_url": pr_url, "messages": [HumanMessage(content=f"✅ Commented on {pr_url}")]}
    except Exception as e:
        return {"messages": [HumanMessage(content=f"❌ Comment failed: {e}")]}
