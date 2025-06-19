import tempfile
from pathlib import Path
from git import Repo, GitCommandError

from langchain_core.messages import HumanMessage
from src.core.state import DevAgentState


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