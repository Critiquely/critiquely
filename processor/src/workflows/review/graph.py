"""LangGraph definition for the code review workflow."""

from functools import partial
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.nodes import (
    clone_repo,
    create_branch,
    commit_code,
    push_code,
    pr_repo,
    comment_on_original_pr,
)
from src.tools.mcp import get_mcp_client
from src.utils.mermaid import save_mermaid_png

from .nodes import inspect_files, apply_recommendations_with_mcp
from .routers import has_more_files_to_inspect, has_tool_invocation
from .state import ReviewState


async def build_review_graph(
    *,
    llm_model: str = "claude-sonnet-4-5-20250929",
    checkpointer: Optional[object] = None,
) -> StateGraph:
    """Build the code review workflow graph.

    This function constructs a LangGraph StateGraph that:
    1. Clones the repository
    2. Creates a new branch for improvements
    3. Inspects modified files for recommendations
    4. Applies recommendations using MCP tools
    5. Commits and pushes changes
    6. Creates a PR and comments on the original

    Args:
        llm_model: The Anthropic model to use for review.
        checkpointer: Optional checkpointer for state persistence.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    async with get_mcp_client() as client:
        tools = await client.get_tools()
        llm = ChatAnthropic(model=llm_model)
        llm_with_tools = llm.bind_tools(tools)

        memory = checkpointer or MemorySaver()

        graph_builder = StateGraph(ReviewState)
        tool_node = ToolNode(tools)

        # ── Nodes ──
        graph_builder.add_node("clone_repo", clone_repo)
        graph_builder.add_node("create_branch", create_branch)
        graph_builder.add_node("inspect_files", partial(inspect_files, llm))
        graph_builder.add_node("tool_call", tool_node)
        graph_builder.add_node(
            "apply_recommendations",
            partial(apply_recommendations_with_mcp, llm_with_tools),
        )
        graph_builder.add_node("push_code", push_code)
        graph_builder.add_node("commit_code", commit_code)
        graph_builder.add_node("pr_repo", pr_repo)
        graph_builder.add_node("comment_on_original_pr", comment_on_original_pr)

        # ── Edges ──
        graph_builder.set_entry_point("clone_repo")
        graph_builder.add_edge("clone_repo", "create_branch")
        graph_builder.add_edge("create_branch", "inspect_files")
        graph_builder.add_conditional_edges(
            "inspect_files",
            has_more_files_to_inspect,
            {
                "inspect_files": "inspect_files",
                END: "apply_recommendations",
            },
        )
        graph_builder.add_conditional_edges(
            "apply_recommendations",
            has_tool_invocation,
            {
                "tools": "tool_call",
                END: "push_code",
            },
        )
        graph_builder.add_edge("tool_call", "commit_code")
        graph_builder.add_edge("commit_code", "apply_recommendations")
        graph_builder.add_edge("push_code", "pr_repo")
        graph_builder.add_edge("pr_repo", "comment_on_original_pr")

        # ── Compile ──
        graph = graph_builder.compile(checkpointer=memory)

        # ── Visualize the graph ──
        save_mermaid_png(graph)

        return graph
