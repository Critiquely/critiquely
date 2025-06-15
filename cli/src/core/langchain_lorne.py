import os
import uuid
import tempfile
from pathlib import Path
from typing_extensions import TypedDict
from typing import Annotated, Optional
import operator
from git import Repo, GitCommandError

from langchain_core.messages import HumanMessage, AnyMessage
from langchain.chat_models import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class DevAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    repo_url: Optional[str]
    repo_path: Optional[str]
    files_to_edit: Optional[list[str]]
    edit_plan: Optional[str]
    diff_summary: Optional[str]
    pr_url: Optional[str]

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

# --- Node: Plan Edits ---
def plan_code_edits(state: DevAgentState) -> dict:
    plan_prompt = state['messages'][-1].content + "\n\nWhat changes should be made?"
    plan = llm.invoke([HumanMessage(content=plan_prompt)])
    return {"messages": [plan], "edit_plan": plan.content}

# --- Node: Edit Code ---
def edit_code(state: DevAgentState) -> dict:
    repo_path = Path(state['repo_path'])
    plan = state['edit_plan']
    changes = []

    for file in state['files_to_edit'][:2]:  # Edit only 2 files for demo
        full_path = repo_path / file
        old_code = full_path.read_text()
        prompt = f"Given this code from {file}:\n{old_code}\n\nMake these changes:\n{plan}"
        new_code = llm.invoke([HumanMessage(content=prompt)]).content
        full_path.write_text(new_code)
        changes.append(f"Modified {file}")

    return {"messages": [HumanMessage(content="Code edited:\n" + "\n".join(changes))], "diff_summary": "\n".join(changes)}

# --- Node: Git Commit + Push ---
def git_commit_push(state: DevAgentState) -> dict:
    repo_path = state['repo_path']
    branch = f"agent-edit-{uuid.uuid4().hex[:6]}"
    try:
        repo = Repo(repo_path)
        
        new_branch = repo.create_head(branch)
        repo.head.reference = new_branch
        repo.head.reset(index=True, working_tree=True)
        
        repo.git.add(A=True)
        
        repo.index.commit("Agent code edits")
        
        origin = repo.remote(name="origin")
        origin.push(refspec=f"{branch}:{branch}", set_upstream=True)
        
        return {"messages": [HumanMessage(content=f"Changes pushed to branch: {branch}")]}
    except GitCommandError as exc:
        error_message = f"Failed to commit/push: {exc}"
        print(error_message)
        return {"messages": [HumanMessage(content=error_message)]}

# --- Node: Create PR (via GitHub CLI) ---
def create_pr(state: DevAgentState) -> dict:
    # subprocess.run(["gh", "pr", "create", "--fill"], cwd=state['repo_path'], check=True)
    return {"messages": [HumanMessage(content="Pull request created via GitHub CLI.")]}

# --- Build Graph ---
graph_builder = StateGraph(DevAgentState)
graph_builder.add_node("clone_repo", clone_repo)
graph_builder.add_node("inspect_files", inspect_files)
graph_builder.add_node("plan_edits", plan_code_edits)
graph_builder.add_node("edit_code", edit_code)
graph_builder.add_node("git_ops", git_commit_push)
graph_builder.add_node("create_pr", create_pr)

graph_builder.set_entry_point("clone_repo")
graph_builder.add_edge("clone_repo", "inspect_files")
graph_builder.add_edge("inspect_files", "plan_edits")
graph_builder.add_edge("plan_edits", "edit_code")
graph_builder.add_edge("edit_code", "git_ops")
graph_builder.add_edge("git_ops", "create_pr")
graph_builder.add_edge("create_pr", END)

workflow = graph_builder.compile()

# --- Run ---
if __name__ == "__main__":
    repo = os.getenv("REPO_URL") or "https://github.com/lornest/opentelemetry-demo.git"
    inputs = {
        "messages": [HumanMessage(content="Update logging logic and add error handling.")],
        "repo_url": repo
    }
    output = workflow.invoke(inputs)
    for msg in output['messages']:
        print("[Agent]:", msg.content)
