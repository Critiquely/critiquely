from typing import Optional

from uuid import uuid4
import json
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.nodes.git import clone_repo

from src.state.state import DevAgentState

async def build_graph(
    *,
    checkpointer: Optional[object] = None,
) -> StateGraph:
    """Build and compile the LangGraph workflow.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                     Defaults to MemorySaver if not provided.

    Returns:
        Compiled StateGraph ready for execution.

    Note:
        When adding MCP tool nodes, initialize the MCP client context in run_graph()
        where the graph is executed, not here. This ensures the client remains open
        during graph execution.
    """
    memory = checkpointer or MemorySaver()

    graph_builder = StateGraph(DevAgentState)

    # ── Nodes ──
    graph_builder.add_node("clone_repo", clone_repo)

    # ── Edges ──
    graph_builder.set_entry_point("clone_repo")
    graph_builder.add_edge("clone_repo", END)

    # ── Compile ──
    graph = graph_builder.compile(checkpointer=memory)

    return graph


async def run_graph(
    repo_url: str, original_pr_url: str, base_branch: str, modified_files: str
):
    """Execute the LangGraph workflow for code review processing.

    Args:
        repo_url: GitHub repository URL to clone and review.
        original_pr_url: URL of the original pull request being reviewed.
        base_branch: Name of the base branch to clone.
        modified_files: JSON string containing list of modified files.
                       Will be parsed into list[dict].

    Note:
        This function streams the graph execution and logs assistant messages.
        Each graph event contains state updates from the executed nodes.
    """
    # Build the graph
    graph = await build_graph()

    # Define the input state
    input_state = {
        "repo_url": repo_url,
        "original_pr_url": original_pr_url,
        "base_branch": base_branch,
        "modified_files": json.loads(modified_files),
    }

    config = {"configurable": {"thread_id": str(uuid4())}}

    # Stream the output
    async for event in graph.astream(input_state, config):
        for value in event.values():
            content = value["messages"][-1].content
            logging.info(f"🤖 Assistant: {content}")