import tempfile
import json
from pathlib import Path
from git import Repo, GitCommandError

from langgraph.graph import END
from langchain_core.messages import HumanMessage
from src.core.state import DevAgentState

def route_tools(state: DevAgentState):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return END

# --- Node: Clone Repo ---
def clone_repo(state: DevAgentState) -> dict:
    path = tempfile.mkdtemp()
    print(f"Cloning repo to {path}...")
    if not state.get('repo_url'):
        return {'messages': [HumanMessage(content="Error: No repository URL provided.")]}
    print( state['repo_branch'])
    try:
        Repo.clone_from(
            state['repo_url'],
            path,
            branch=state['repo_branch'],
            depth=1,
            single_branch=True
        )
        print(f"Cloned {state['repo_url']} to {path}")
        return {'repo_path': path, 'messages': [HumanMessage(content=f"Cloned repo to {path}")]}
    except GitCommandError as exc:
        error_message = f"Failed to clone: {exc}"
        print(error_message)
        return {'messages': [HumanMessage(content=error_message)]}

# --- Node: Inspect Files ---
def inspect_files(llm, state: DevAgentState) -> dict:
    """
    LangGraph node that reviews the *first* pending file.

    Expected keys in `state` before call:
        repo_path: str
        modified_files: list[dict]  # [{filename, lines_changed, ...}]
        messages: list[BaseMessage]  (optional)

    Side effects on `state`:
        current_file: str
        current_file_content: str
        last_review: str
        messages: list[...]  (review prompt + response appended)
        modified_files: 1st entry popped
    """
    # ── 1) Guard: nothing left to review ───────────────────────────────────
    if not state.get("modified_files"):
        return state

    entry = state["modified_files"].pop(0)         # remove first item

    # ── 2) Load file text ──────────────────────────────────────────────────
    fname = entry["filename"]
    fpath = Path(state["repo_path"]) / fname
    file_text = fpath.read_text(encoding="utf-8")
    lines_changed = entry["lines_changed"]

    state["current_file"] = fname
    state["current_file_content"] = file_text
    state["current_file_lines_changed"] = lines_changed

    # # ── 3) Build a snippet of only the changed lines (for shorter prompts) ─
    # changed = entry.get("lines_changed", [])
    # if changed:
    #     lines = file_text.splitlines()
    #     snippet = "\n".join(
    #         f"{ln:>4}: {lines[ln-1]}" for ln in changed if 0 < ln <= len(lines)
    #     )
    # else:
    #     snippet = file_text[:4_000]  # fallback / truncate if diff missing

    # ── 3) Ask the LLM for a review ────────────────────────────────────────
    prompt = HumanMessage(
        content=(
            "You are a senior Python reviewer.\n\n"
            f"File: {fpath}\n"
            f"Modified lines: {lines_changed}\n\n"
            "You may review other parts of the file **only if they are directly impacted by the modified lines**.\n"
            "Do **not** comment on unrelated or unmodified parts of the file.\n"
            "Focus your review on how the modified lines affect the file's overall functionality, readability, performance, reliability, or security.\n\n"
            "Provide **only high-impact recommendations**, avoiding cosmetic or low-value style suggestions.\n\n"
            "List **at most 3** recommendations.\n"
            "If there are no high-value suggestions, return an array with one object that includes the filename and an empty recommendations list.\n\n"
            "**Do not explain, justify, or include any text outside the JSON array. Return only the JSON array.**\n\n"
            "Output format:\n"
            "[\n"
            "  {\n"
            "    \"file\": \"<filename>\",\n"
            "    \"recommendations\": [\"...\", \"...\"]\n"
            "  }\n"
            "]\n\n"
            f"File contents:\n{file_text}"
        )
    )
    response = llm.invoke([prompt])

    # ── 5) Save conversation + latest review text ──────────────────────────
    state.setdefault("messages", []).extend([prompt, response])

    print("response", response)

    try:
        parsed = json.loads(response.content.strip())
    except json.JSONDecodeError as e:
        print("Failed to parse JSON:", e)
        parsed = []  # fallback
    state.setdefault("recommendations", []).extend(parsed)

    return state

def apply_recommendations_with_mcp(llm_with_tools, state: DevAgentState) -> DevAgentState:
    if not state["recommendations"]:
        return state

    current_rec = state["recommendations"].pop(0)
    file_path = Path(current_rec["file"])
    recs = current_rec.get("recommendations", [])

    if not recs or not file_path.exists():
        return state

    file_text = file_path.read_text(encoding="utf-8")
    instructions = "\n".join(f"- {r}" for r in recs)

    prompt = (
        f"You are a coding assistant. A user has asked for edits to a source file.\n\n"
        f"File path: {file_path}\n\n"
        f"File contents:\n{file_text}\n\n"
        f"Requested changes:\n{instructions}\n\n"
        f"Decide which tool to call from your available toolset to perform these changes. "
        f"Only return the tool invocation with no explanation."
    )

    # Let the LLM choose the tool to call
    result = llm_with_tools.invoke([HumanMessage(content=prompt)])

    print(result)

    state.setdefault("messages", []).append(
        HumanMessage(content=f"Processed {file_path.name} via LLM tool choice.")
    )
    state.setdefault("updated_files", []).append(str(file_path))

    print(f"Remaining recommendations: {state.get('recommendations', [])}")

    return state