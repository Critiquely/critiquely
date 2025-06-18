# src/core/review.py
from src.core.graph import build_graph
from src.utils.git import clone_git_repo

from langchain_anthropic import ChatAnthropic
from src.tools.mcp import get_mcp_client



async def run_review_graph(repo_url: str, branch: str, modified_files: str):

    tools = await get_mcp_client.get_tools()
    llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
    llm_with_tools = llm.bind_tools(tools)

    local_path = clone_git_repo(repo_url, branch)

    # Build the graph
    graph = build_graph(llm_with_tools)

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
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)