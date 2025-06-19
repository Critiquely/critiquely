import tempfile
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
    
    try:
        Repo.clone_from(
            state['repo_url'],
            path,
            branch=state.get('branch', 'main'),
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
def inspect_files(llm_with_tools, state: DevAgentState) -> dict:
    prompt = "Make recommendations on how to improve the code that has been modified. The code can be foune in " + state['repo_path'] + "and the following has been modified" + state['modified_files']
    response = llm_with_tools.invoke(prompt)
    return {
        "messages": [HumanMessage(prompt), response],
    }