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

        def continue_to_recommendations(state: DevAgentState):
            recommendations = state.get('recommendations', [])
            
            if not recommendations:
                return []
            
            # Group recommendations by file
            file_groups = {}
            for rec in recommendations:
                file_path = rec.get("file", "")
                if file_path not in file_groups:
                    file_groups[file_path] = []
                file_groups[file_path].append(rec)
            
            # Create one Send per file (with all its recommendations)
            sends = []
            for file_path, file_recs in file_groups.items():
                subgraph_state = {
                    "messages": [],
                    "clone_path": state.get("clone_path"),
                    "file_recommendations": file_recs,  # All recommendations for this file
                    "target_file": file_path,
                    "updated_files": []
                }
                sends.append(Send("apply_recommendation_graph", subgraph_state))
            
            return sends
        
        def route_after_inspection(state: DevAgentState):
            # Since inspect_files now processes all files at once, 
            # we directly proceed to recommendations
            return continue_to_recommendations(state)

        memory = checkpointer or MemorySaver()

        tool_node = ToolNode(tools)

        # Subgraph

        subgraph_builder = StateGraph(DevAgentState)
        subgraph_builder.add_node(
            "apply_recommendations",
            partial(apply_recommendations_with_mcp, llm_with_tools),
        )
        subgraph_builder.add_node("tool_call", tool_node)

        subgraph_builder.set_entry_point("apply_recommendations")
        subgraph_builder.add_conditional_edges(
            "apply_recommendations",
            has_tool_invocation,
            {
                "tools": "tool_call",
                END: END,
            },
        )
        subgraph_builder.add_edge("tool_call", END)
        compiled_subgraph = subgraph_builder.compile()
        
        # Create a wrapper that ensures only safe state keys are returned
        async def apply_recommendation_graph(state):
            result = await compiled_subgraph.ainvoke(state)
            # Only return keys that are safe for concurrent updates
            safe_result = {
                "messages": result.get("messages", []),
                "updated_files": result.get("updated_files", [])
            }
            return safe_result

        # Main Graph
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
        generate_recommendations_workflow.add_node("agent", call_agent)
        generate_recommendations_workflow.add_node("tools", tool_node)
        generate_recommendations_workflow.set_entry_point("agent")
        generate_recommendations_workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "tools",
                "end": END,
            },
        )
        generate_recommendations_workflow.add_edge("tools", "agent")
        generate_recommendations_graph = generate_recommendations_workflow.compile()
        
        # ── Apply Recommendations Subgraph ── (this one was WIP)
        apply_recommendations_workflow = StateGraph(RecommendationsState)
        apply_recommendations_workflow.add_node("apply_recommendations", apply_recommendations_with_mcp)
        apply_recommendations_workflow.add_node("tool_call", tool_node)
        apply_recommendations_workflow.set_entry_point("apply_recommendations")
        apply_recommendations_workflow.add_conditional_edges(
            "apply_recommendations",
            has_tool_invocation,
            {
                "tools": "tool_call",
                END: END,
            },
        )
        apply_recommendations_workflow.add_edge("tool_call", END)
        apply_recommendations_graph = apply_recommendations_workflow.compile()


        # ── Edges ──
        workflow.set_entry_point("clone_repo")
        workflow.add_edge("clone_repo", "create_branch")
        workflow.add_edge("create_branch", "inspect_files")
        workflow.add_conditional_edges(
            "inspect_files",
            route_after_inspection
        )
        
        workflow.add_edge("apply_recommendation_graph", "commit_all_changes")
        workflow.add_edge("commit_all_changes", "push_code")
        workflow.add_edge("push_code", "pr_repo")
        workflow.add_edge("pr_repo", "comment_on_original_pr")
        # ── Compile ──
        graph = workflow.compile(checkpointer=memory)

        # ── Visualise the graph ──
        save_mermaid_png(graph)

        return graph
