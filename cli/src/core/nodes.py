import tempfile
import json
from uuid import uuid4
import os
import logging
from urllib.parse import urlparse, urlunparse, quote
from pathlib import Path

from git import Repo, GitCommandError
from github import Github
from github import Auth

from langgraph.graph import END
from langchain_core.messages import HumanMessage
from src.core.state import DevAgentState
from src.utils.fs_utils import get_temp_dir

# Use the root logger configuration from CLI
logger = logging.getLogger(__name__)


def get_state_value(state: DevAgentState, key: str) -> str:
    """Raise a ValueError if state[key] is missing/empty after strip()."""
    if key not in state:
        msg = f"❌ '{key}' missing from state."
        logger.error(msg)
        raise KeyError(msg)

    val = state[key]

    if val is None:
        msg = f"❌ '{key}' is None."
        logger.error(msg)
        raise ValueError(msg)

    if isinstance(val, str):
        val = val.strip()
        if val == "":
            msg = f"❌ '{key}' is blank."
            logger.error(msg)
            raise ValueError(msg)

    return val


def create_github_https_url(https_url: str, token_env="GITHUB_TOKEN") -> str:
    token = os.getenv(token_env, "").strip()
    if not token:
        msg = "❌ Error: GITHUB_TOKEN is unset or empty."
        logger.error(msg)
        raise ValueError(msg)
    if not https_url.startswith("https://"):
        msg = "❌ Error: SSH URL has been provided. The app will not handle these.."
        logger.error(msg)
        raise ValueError(msg)

    parts = urlparse(https_url)
    auth = quote(token, safe="")
    url = urlunparse(parts._replace(netloc=f"{auth}@{parts.netloc}"))

    return url


###############################################################################
#                                R O U T E R S                                #
###############################################################################


# --- Node: Route to tools ---
def route_tools(state: DevAgentState):
    """
    Route to the ToolNode if the last message has tool calls; otherwise END.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        error = f"No messages found to route: {state}"
        logger.error(f"❌ {error}")
        raise ValueError(error)

    has_tools = bool(getattr(ai_message, "tool_calls", None))

    if has_tools:
        tool_name = ai_message.tool_calls[0]["name"]
        logger.info(f"🚀 Routing to tool: {tool_name}")
        return "tools"

    logger.info("🏁 Routing to END node")
    return END


###############################################################################
#                                G I T   N O D E S                            #
###############################################################################


# --- Node: Clone Repo ---
def clone_repo(state: DevAgentState) -> dict:
    repo_url = get_state_value(state, "repo_url")
    branch = get_state_value(state, "repo_branch")

    git_url = create_github_https_url(repo_url)

    try:
        temp_dir = tempfile.mkdtemp(dir=get_temp_dir())
        logger.info(f"🔄 Cloning {repo_url}@{branch} into {temp_dir}")
        repo = Repo.clone_from(
            git_url, temp_dir, branch=branch, depth=1, single_branch=True
        )
        # Scrub token from remote config
        repo.remote().set_url(repo_url)

        msg = f"✅ Cloned {repo_url}@{branch} to {temp_dir}"
        logger.info(msg)
        return {"repo_path": temp_dir, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"❌ Failed to clone {repo_url}@{branch}: {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


# --- Node: Create Branch ---
def create_branch(state: DevAgentState) -> DevAgentState:
    repo_path = get_state_value(state, "repo_path")
    branch = get_state_value(state, "repo_branch")

    try:
        repo = Repo(repo_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"❌ Error: Cannot open repo at '{repo_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    branch_name = f"critiquely/{branch}-improvements-{uuid4().hex[:8]}"
    try:
        logger.info(f"🔄 Creating a new branch: {branch_name}")
        branch = repo.create_head(branch_name)
        branch.checkout()

        msg = f"✅ New branch created: {branch_name}"
        logger.info(msg)
        return {
            "new_branch": branch_name,
            "messages": [HumanMessage(content=msg)],
        }

    except GitCommandError as exc:
        error = f"❌ Failed to create {branch_name}: {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


# --- Node: Create Branch ---
def commit_code(state: DevAgentState) -> DevAgentState:
    repo_path = get_state_value(state, "repo_path")
    branch = get_state_value(state, "new_branch")
    repo_url = get_state_value(state, "repo_url")
    current_recommendation = get_state_value(state, "current_recommendation")
    print(current_recommendation)

    git_url = create_github_https_url(repo_url)
    recommendation_summary = current_recommendation.get("summary", [])

    # 2) Open the repo
    try:
        repo = Repo(repo_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"❌ Error: Cannot open repo at '{repo_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # 3) Inject token into the origin URL
    origin = repo.remote(name="origin")
    origin.set_url(git_url)

    # Stage & commit
    try:
        # Stage all changes (new, modified, deleted)
        repo.git.add("--all")
        # Create a commit
        repo.index.commit(recommendation_summary)
        msg = f"📝 Committed changes to '{branch}'"
        logger.info(msg)
        return {"messages": [HumanMessage(content=msg)]}
    except GitCommandError as exc:
        msg = f"❌ Failed to add/commit changes: {exc}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}


# --- Node: Push Code ---
def push_code(state: DevAgentState) -> DevAgentState:
    repo_path = get_state_value(state, "repo_path")
    branch = get_state_value(state, "new_branch")
    repo_url = get_state_value(state, "repo_url")

    git_url = create_github_https_url(repo_url)

    # 2) Open the repo
    try:
        repo = Repo(repo_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"❌ Error: Cannot open repo at '{repo_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # 3) Inject token into the origin URL
    origin = repo.remote(name="origin")
    origin.set_url(git_url)

    # 4) Push
    try:
        logger.info(f"🔄 Pushing branch '{branch}' to origin")
        origin.push(refspec=f"{branch}:{branch}")
        msg = f"✅ Pushed branch '{branch}' to origin"
        logger.info(msg)
        return {"new_branch": branch, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"❌ Failed to push to '{branch}': {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


# --- Node: Push Code ---
def pr_code(state: DevAgentState) -> DevAgentState:
    repo_url = get_state_value(state, "repo_url")
    repo_path = get_state_value(state, "repo_path")
    original_branch = get_state_value(state, "repo_branch")
    new_branch = get_state_value(state, "new_branch")

    git_url = create_github_https_url(repo_url)

    # 2) Open the repo
    try:
        repo = Repo(repo_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"❌ Error: Cannot open repo at '{repo_path}': {e}"
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # 3) Inject token into the origin URL
    origin = repo.remote(name="origin")
    origin.set_url(git_url)

    # 4) Push
    try:
        logger.info(f"🔄 Pushing branch '{branch}' to origin")
        origin.push(refspec=f"{branch}:{branch}")
        msg = f"✅ Pushed branch '{branch}' to origin"
        logger.info(msg)
        return {"new_branch": branch, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"❌ Failed to push to '{branch}': {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}


# --- Node: Clone Repo ---
def pr_repo(state: DevAgentState) -> dict:
    repo_url = get_state_value(state, "repo_url")
    base_branch = get_state_value(state, "repo_branch")
    head_branch = get_state_value(state, "new_branch")

    title = f"Critiquely improvements"
    body = "Automated code review fixes and improvements."

    # Retrieve GitHub Token
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        msg = "❌ GITHUB_TOKEN is unset or empty."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Retrieve repo name from URL
    repo_name = urlparse(repo_url).path.lstrip("/").removesuffix(".git")

    # Access the GitHub Repo
    try:
        gh = Github(auth=Auth.Token(token))
        repo = gh.get_repo(repo_name)
    except GithubException as exc:
        msg = f"❌ Failed to access repo '{repo_name}': {exc.data.get('message', exc)}"
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
        msg = f"✅ Opened PR #{pr.number}: {pr.html_url}"
        logger.info(msg)
        return {
            "pr_number": pr.number,
            "pr_url": pr.html_url,
            "messages": [HumanMessage(content=msg)],
        }

    except GithubException as exc:
        msg = (
            f"❌ Failed to open PR {head_branch} → {base_branch}: "
            f"{exc.data.get('message', exc)}"
        )
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}


###############################################################################
#                                L L M   N O D E S                            #
###############################################################################


# --- Node: Inspect Files ---
def inspect_files(llm, state: DevAgentState) -> dict:
    if not state.get("modified_files"):
        logger.info("✅ No modified files to inspect. Skipping.")
        return state

    entry = state["modified_files"].pop(0)
    fname = entry.get("filename")
    fpath = Path(state.get("repo_path", "")) / fname

    try:
        file_text = fpath.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"❌ Could not read file {fpath}: {e}")
        state.setdefault("messages", []).append(HumanMessage(content=msg))
        return state

    lines_changed = entry.get("lines_changed", [])
    logger.info(f"🔍 Inspecting {fname} (lines {lines_changed})")

    state.update(
        {
            "current_file": fname,
            "current_file_content": file_text,
            "current_file_lines_changed": lines_changed,
        }
    )

    prompt = HumanMessage(
        content=(
            "You are a senior Python reviewer.\n\n"
            f"File: {fpath}\n"
            f"Modified lines: {lines_changed}\n\n"
            "Review only sections directly impacted by the modifications. "
            "Provide up to 3 high-impact recommendations in JSON array only.\n\n"
            "Output format:\n"
            "[{'file':'<filename>','summary':'<github commit style summary using conventional commit syntax>','recommendation':'<recommendation>'},{'file':'<filename>','summary':'<github commit style summary>','recommendation':'<recommendation>'}]\n\n"
            "You can have multiple objects for a specific file if there are multple recommendations\n\n"
            f"File contents:\n{file_text}"
        )
    )
    state.setdefault("messages", []).append(prompt)
    logger.info("💬 Sending review prompt to LLM")
    response = llm.invoke([prompt])
    logger.info("✅ LLM response received")
    state["messages"].append(response)

    try:
        parsed = json.loads(response.content.strip())
    except json.JSONDecodeError as e:
        msg = f"❌ Failed to parse JSON: {e}"
        logger.error(msg)
        parsed = []

    state.setdefault("recommendations", []).extend(parsed)
    return state


def apply_recommendations_with_mcp(
    llm_with_tools, state: DevAgentState
) -> DevAgentState:
    recs_list = state.get("recommendations", [])
    if not recs_list:
        logger.info("✅ No recommendations to apply. Skipping.")
        return state

    current = recs_list.pop(0)
    state.update({"current_recommendation": current})
    file_path = Path(current.get("file", ""))
    recs = current.get("recommendation", [])

    if not recs:
        logger.warning(f"❌ No recommendations for {file_path}")
        return state
    if not file_path.exists():
        logger.error(f"❌ File not found: {file_path}")
        return state

    file_text = file_path.read_text(encoding="utf-8")
    logger.info(f"🔍 Applying recommendation to {file_path.name}")

    instructions = "\n".join(f"- {r}" for r in recs)
    prompt = HumanMessage(
        content=(
            "You are a coding assistant. A user requested edits to a source file.\n\n"
            f"File path: {file_path}\n\n"
            f"File contents:\n{file_text}\n\n"
            f"Requested changes:\n{instructions}\n\n"
            "Choose and invoke a tool from your toolkit. Return only the invocation."
        )
    )
    state.setdefault("messages", []).append(prompt)
    logger.info("💬 Invoking LLM with tools")

    result = llm_with_tools.invoke([prompt])
    logger.info("✅ Received tool invocation from LLM")
    state["messages"].append(result)

    state.setdefault("updated_files", []).append(str(file_path))
    logger.info(
        f"✅ Applied recommendations to {file_path.name}; {len(recs_list)} remaining"
    )
    return state
