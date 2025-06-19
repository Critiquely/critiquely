
from langgraph.graph import StateGraph, END
from functools import partial
from src.tools.mcp import get_mcp_client
from langchain_anthropic import ChatAnthropic

from langgraph.prebuilt import ToolNode

from langgraph.checkpoint.memory import MemorySaver


from src.core.nodes import clone_repo, inspect_files, route_tools
from src.core.state import DevAgentState

async def build_graph():
    async with get_mcp_client() as client:  # ✅ This is correct
        tools = await client.get_tools()
        llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
        llm_with_tools = llm.bind_tools(tools)

        memory = MemorySaver()

        graph_builder = StateGraph(DevAgentState)

        def route_more(state: DevAgentState):
            return "inspect_files" if state["modified_files"] else END

        tool_node = ToolNode(tools)

        graph_builder.add_node("clone_repo", clone_repo)
        graph_builder.add_node("inspect_files", partial(inspect_files,llm))
        graph_builder.add_node("tool_call", tool_node)

        graph_builder.set_entry_point("clone_repo")
        graph_builder.add_edge("clone_repo", "inspect_files")
    
        graph_builder.add_conditional_edges(
            "inspect_files",
            route_more,
            {
                "inspect_files": "inspect_files",  # back into the node
                END: END,                           # finish when empty
            },
        )


        return graph_builder.compile(checkpointer=memory)