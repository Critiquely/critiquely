import tempfile
import json
from uuid import uuid4
import os
import logging
from urllib.parse import urlparse, urlunparse, quote
from pathlib import Path
from git import Repo, GitCommandError

from langgraph.graph import END
from langchain_core.messages import HumanMessage
from src.core.state import DevAgentState

# Use the root logger configuration from CLI
logger = logging.getLogger(__name__)


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

# --- Node: Clone Repo ---
def clone_repo(state: DevAgentState) -> dict:
    repo_url = state.get("repo_url", "").strip()
    branch   = state.get("repo_branch", "").strip()

    if not repo_url:
        msg = "❌ Error: No repository URL provided."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not branch:
        msg = "❌ Error: No repository branch provided."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        msg = "❌ Error: GITHUB_TOKEN is unset or empty."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Percent-encode and inject token
    token_enc = quote(token, safe="")
    parsed    = urlparse(repo_url)
    auth_url  = urlunparse(parsed._replace(netloc=f"{token_enc}@{parsed.netloc}"))

    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"🔄 Cloning {repo_url}@{branch} into {temp_dir}")
        repo = Repo.clone_from(
            auth_url,
            temp_dir,
            branch=branch,
            depth=1,
            single_branch=True
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

    state.update({
        "current_file": fname,
        "current_file_content": file_text,
        "current_file_lines_changed": lines_changed
    })

    prompt = HumanMessage(content=(
        "You are a senior Python reviewer.\n\n"
        f"File: {fpath}\n"
        f"Modified lines: {lines_changed}\n\n"
        "Review only sections directly impacted by the modifications. "
        "Provide up to 3 high-impact recommendations in JSON array only.\n\n"
        "Output format:\n"
        "[{'file':'<filename>','recommendations':['...','...']}]\n\n"
        f"File contents:\n{file_text}"
    ))
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


def apply_recommendations_with_mcp(llm_with_tools, state: DevAgentState) -> DevAgentState:
    recs_list = state.get("recommendations", [])
    if not recs_list:
        logger.info("✅ No recommendations to apply. Skipping.")
        return state

    current = recs_list.pop(0)
    file_path = Path(current.get("file", ""))
    recs      = current.get("recommendations", [])

    if not recs:
        logger.warning(f"❌ No recommendations for {file_path}")
        return state
    if not file_path.exists():
        logger.error(f"❌ File not found: {file_path}")
        return state

    file_text = file_path.read_text(encoding="utf-8")
    logger.info(f"🔍 Applying {len(recs)} recommendations to {file_path.name}")

    instructions = "\n".join(f"- {r}" for r in recs)
    prompt = HumanMessage(content=(
        "You are a coding assistant. A user requested edits to a source file.\n\n"
        f"File path: {file_path}\n\n"
        f"File contents:\n{file_text}\n\n"
        f"Requested changes:\n{instructions}\n\n"
        "Choose and invoke a tool from your toolkit. Return only the invocation."
    ))
    state.setdefault("messages", []).append(prompt)
    logger.info("💬 Invoking LLM with tools")

    result = llm_with_tools.invoke([prompt])
    logger.info("✅ Received tool invocation from LLM")
    state["messages"].append(result)

    state.setdefault("updated_files", []).append(str(file_path))
    logger.info(f"✅ Applied recommendations to {file_path.name}; {len(recs_list)} remaining")
    return state

# --- Node: Create Branch ---
def create_branch( state: DevAgentState) -> DevAgentState:
    repo_path = state.get("repo_path", "").strip()
    branch   = state.get("repo_branch", "").strip()

    if not repo_path:
        msg = "❌ Error: No repository path provided."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not branch:
        msg = "❌ Error: No repository branch provided."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    try:
        repo = Repo(repo_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"❌ Error: Cannot open repo at '{repo_path}': {e}"
        logger.error(msg)
        return {"messages":[HumanMessage(content=msg)]}

    new_branch = f"critiquely/{branch}-improvements-{uuid4().hex[:8]}"
    try:
        logger.info(f"🔄 Creating a new branch: {new_branch}")
        new_branch = repo.create_head(new_branch)
        new_branch.checkout()

        msg = f"✅ New branch created: {new_branch}"
        logger.info(msg)
        return {"new_branch": new_branch, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"❌ Failed to create {new_branch}: {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}

# --- Node: Create Branch ---
def push_code( state: DevAgentState) -> DevAgentState:
    repo_path = state.get("repo_path", "").strip()
    branch   = state.get("new_branch", "")

    if not repo_path:
        msg = "❌ Error: No repository path provided."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    if not branch:
        msg = "❌ Error: No repository branch provided."
        logger.error(msg)
        return {"messages": [HumanMessage(content=msg)]}

    try:
        repo = Repo(repo_path)
    except (NoSuchPathError, InvalidGitRepositoryError) as e:
        msg = f"❌ Error: Cannot open repo at '{repo_path}': {e}"
        logger.error(msg)
        return {"messages":[HumanMessage(content=msg)]}

    try:
        logger.info(f"🔄 Pushing code to {branch}")
        origin = repo.remote(name="origin")
        # Push local branch X to remote branch X
        origin.push(refspec=f"{branch}:{branch}")

        msg = f"✅ Pushed code to {branch}"
        logger.info(msg)
        return {"new_branch": branch, "messages": [HumanMessage(content=msg)]}

    except GitCommandError as exc:
        error = f"❌ Failed to push to {new_brnach}: {exc}"
        logger.error(error)
        return {"messages": [HumanMessage(content=error)]}