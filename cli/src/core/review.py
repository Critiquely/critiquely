# src/core/review.py
from src.core.graph import build_graph

from uuid import uuid4
import json
import logging



from langchain_anthropic import ChatAnthropic
from src.tools.mcp import get_mcp_client



async def run_review_graph(repo_url: str, repo_branch: str, modified_files: str):
    print(repo_branch)
    # Build the graph
    graph = await build_graph()

    # Define the input state
    input_state = {
        "repo_url": repo_url,
        "repo_branch": repo_branch,
        "modified_files": json.loads(modified_files),
        "messages": []
    }

    config = {
        "configurable": {
            "thread_id": str(uuid4())  # or any unique session ID
        }
    }

    print("CONFIG",config)

    # Stream the output
    async for event in graph.astream(input_state, config):
        for value in event.values():
            content = value["messages"][-1].content
            logging.info(f"🤖 Assistant: {content}")


    