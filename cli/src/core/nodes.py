import tempfile
from pathlib import Path
from git import Repo, GitCommandError

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from src.core.state import DevAgentState

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")

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
def inspect_files(state: DevAgentState) -> dict:
    repo_path = Path(state['repo_path'])
    files = list(repo_path.glob("**/*.py"))[:5]
    summaries = {str(f): f.read_text()[:300] for f in files}
    content = "\n\n".join([f"{k}: {v}" for k, v in summaries.items()])
    return {"messages": [HumanMessage(content=f"Here are some files to consider:\n{content}")],
            "files_to_edit": [str(f.relative_to(repo_path)) for f in files]}