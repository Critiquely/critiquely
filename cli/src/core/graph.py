from functools import partial
from pathlib import Path
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.core.nodes import (
    apply_recommendations_with_mcp,
    clone_repo,
    commit_code,
    create_branch,
    inspect_files,
    push_code,
    route_tools,
)
from src.core.state import DevAgentState
from src.tools.mcp import get_mcp_client

# ───────────────────────── Routing helpers ──────────────────────────


def route_more(state: DevAgentState) -> str:
    """Keep inspecting until the modified-file list is empty."""
    return "inspect_files" if state.get("modified_files") else END


def route_after_tool_call(state: DevAgentState) -> str:
    """
    If the previous tool interaction produced edits, go commit them;
    otherwise continue to push.
    """
    
    return "commit_code" if state.get("tool_outputs") else "push_code"


async def build_graph(
    *,
    llm_model: str = "claude-3-5-sonnet-latest",
    checkpointer: Optional[object] = None,
):
    async with get_mcp_client() as client:
        tools = await client.get_tools()
        llm = ChatAnthropic(model=llm_model)
        llm_with_tools = llm.bind_tools(tools)

        memory = MemorySaver()

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

        # ── Edges ──
        graph_builder.set_entry_point("clone_repo")
        graph_builder.add_edge("clone_repo", "create_branch")
        graph_builder.add_edge("create_branch", "inspect_files")
        graph_builder.add_conditional_edges(
            "inspect_files",
            route_more,
            {
                "inspect_files": "inspect_files",  # back into the node
                END: "apply_recommendations",                           # finish when empty
            },
        )
        graph_builder.add_conditional_edges(
            "apply_recommendations",
            route_tools,
            {
                "tools": "tool_call",  # back into the node
                END: "push_code",                           # finish when empty
            },
        )
        graph_builder.add_edge("tool_call", "commit_code")
        graph_builder.add_edge("commit_code", "apply_recommendations")

        # ── Compile ──
        graph = graph_builder.compile(checkpointer=memory)

        try:
            png_bytes = graph.get_graph().draw_mermaid_png()
            with open("graph_mermaid.png", "wb") as f:
                f.write(png_bytes)
            print("Saved Mermaid-rendered graph to graph_mermaid.png")
        except Exception as e:
            print(f"Mermaid PNG render failed: {e}")

        return graph

        