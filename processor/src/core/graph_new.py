from functools import partial
from typing import Optional
import logging

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Send


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

from src.utils.routers import has_tool_invocation
from src.utils.mermaid import save_mermaid_png

logger = logging.getLogger(__name__)



async def build_graph(
    *,
    llm_model: str = "claude-3-5-sonnet-latest",
    checkpointer: Optional[object] = None,
) -> StateGraph:
    async with get_mcp_client() as client:
        tools = await client.get_tools()
        llm = ChatAnthropic(model=llm_model)
        llm_with_tools = llm.bind_tools(tools)

        memory = checkpointer or MemorySaver()
        workflow = StateGraph(WorkflowState)

        # ── Main Workflow ──
        workflow.add_node("clone_repo", clone_repo)
        workflow.add_node("generate_recommendations_graph", generate_recommendations_graph)
        workflow.add_node("apply_recommendations_graph", apply_recommendations_graph) 
        workflow.add_node("comment_on_original_pr", comment_on_original_pr)

        workflow.set_entry_point("clone_repo")
        workflow.add_edge("clone_repo", "generate_recommendations_graph")
        workflow.add_conditional_edges("generate_recommendations_graph", implement_recommendations)
        workflow.add_edge("apply_recommendations_graph", "comment_on_original_pr")
        workflow.add_edge("comment_on_original_pr", END)

        graph = workflow.compile(checkpointer=memory)
        
        # ── Subgraphs ──

        # ── Recommendations Subgraph ──
        generate_recommendations_workflow = StateGraph(RecommendationsState)
        generate_recommendations_workflow.add_node("generate_recommendations", generate_recommendations)
        generate_recommendations_workflow.add_node("tools", tool_node)
        generate_recommendations_workflow.set_entry_point("generate_recommendations")
        generate_recommendations_workflow.add_conditional_edges(
            "generate_recommendations",
            should_continue,
            {
                "continue": "tools",
                "end": END,
            },
        )
        generate_recommendations_workflow.add_edge("tools", "generate_recommendations")
        generate_recommendations_graph = generate_recommendations_workflow.compile()
        
        # ── Apply Recommendations Subgraph ──
        apply_recommendations_workflow = StateGraph(RecommendationsState)
        apply_recommendations_workflow.add_node("create_branch", create_branch)
        apply_recommendations_workflow.add_node("apply_recommendations", apply_recommendations)
        apply_recommendations_workflow.add_node("tools", tool_node)
        apply_recommendations_workflow.add_node("commit_code", commit_code)  # Single commit after all parallel work
        apply_recommendations_workflow.add_node("push_code", push_code)
        apply_recommendations_workflow.add_node("pr_repo", pr_repo)

        apply_recommendations_workflow.set_entry_point("create_branch")
        apply_recommendations_workflow.add_edge("create_branch", "apply_recommendations")
        apply_recommendations_workflow.add_conditional_edges(
            "apply_recommendations",
            should_continue,
            {
                "continue": "tools",
                "end": "commit_code",
            },
        )
        apply_recommendations_workflow.add_edge("tools", "apply_recommendations")
        apply_recommendations_workflow.add_edge("commit_code", "push_code")
        apply_recommendations_workflow.add_edge("push_code", "pr_repo")
        apply_recommendations_graph = apply_recommendations_workflow.compile()

        # ── Visualise the graph ──
        save_mermaid_png(graph)

        return graph
