# src/core/review.py
from src.core.graph import build_graph
from src.core.git_utils import clone_git_repo


async def run_review_graph(repo_url: str, branch: str, modified_files: str):
    local_path = clone_git_repo(repo_url, branch)

    # Build the graph
    graph = build_graph()

    # Define the input state
    input_state = {
        "repo_path": local_path,
        "repo_url": repo_url,
        "repo_branch": branch,
        "modified_files": modified_files,
        "messages": []
    }

    # Stream the output
    async for event in graph.astream(input_state):
        print("Graph step:", event)