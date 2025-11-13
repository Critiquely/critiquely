from functools import partial
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.core.nodes import (
    apply_recommendations_with_mcp,
    clone_repo,
    comment_on_original_pr,
    commit_code,
    create_branch,
    inspect_files,
    push_code,
    pr_repo,
)
from src.core.state import DevAgentState
from src.tools.mcp import get_mcp_client

from src.utils.routers import has_more_files_to_inspect, has_tool_invocation
from src.utils.mermaid import save_mermaid_png


async def build_graph(
    *,
    llm_model: str = "claude-sonnet-4-5-20250929",
    checkpointer: Optional[object] = None,
) -> StateGraph:
    async with get_mcp_client() as client:
        tools = await client.get_tools()
        llm = ChatAnthropic(model=llm_model)
        llm_with_tools = llm.bind_tools(tools)

        memory = checkpointer or MemorySaver()

        graph_builder = StateGraph(DevAgentState)
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

        # ── Visualise the graph ──
        save_mermaid_png(graph)

        return graph
