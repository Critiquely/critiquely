from functools import partial
from typing import Optional

from uuid import uuid4
import json
import logging

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.nodes.git import clone_repo

from src.state.state import DevAgentState

from src.tools.mcp import get_mcp_client

async def build_graph(
    *,
    llm_model: str = "claude-sonnet-4-5-20250929",
    checkpointer: Optional[object] = None,
) -> StateGraph:
    async with get_mcp_client() as client:

        memory = checkpointer or MemorySaver()

        graph_builder = StateGraph(DevAgentState)

        # ── Nodes ──
        graph_builder.add_node("clone_repo", clone_repo)
        
        # ── Edges ──
        graph_builder.set_entry_point("clone_repo")

        # ── Compile ──
        graph = graph_builder.compile(checkpointer=memory)

        return graph


async def run_graph(
    repo_url: str, original_pr_url: str, base_branch: str, modified_files: str
):
    # Build the graph
    graph = await build_graph()

    # Define the input state
    input_state = {
        "repo_url": repo_url,
        "original_pr_url": original_pr_url,
        "base_branch": base_branch,
        "modified_files": json.loads(modified_files),
        "messages": [],
    }

    config = {"configurable": {"thread_id": str(uuid4())}}

    # Stream the output
    async for event in graph.astream(input_state, config):
        for value in event.values():
            content = value["messages"][-1].content
            logging.info(f"🤖 Assistant: {content}")