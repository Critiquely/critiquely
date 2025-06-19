
from langgraph.graph import StateGraph, END
from functools import partial
from src.tools.mcp import get_mcp_client
from langchain_anthropic import ChatAnthropic



from src.core.nodes import clone_repo, inspect_files
from src.core.state import DevAgentState

async def build_graph():
    async with get_mcp_client() as client:  # ✅ This is correct
        tools = await client.get_tools()
        llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
        llm_with_tools = llm.bind_tools(tools)

        graph_builder = StateGraph(DevAgentState)

        graph_builder.add_node("clone_repo", clone_repo)
        graph_builder.add_node("inspect_files", partial(inspect_files,llm_with_tools))


        graph_builder.set_entry_point("clone_repo")
        graph_builder.add_edge("clone_repo", "inspect_files")
        graph_builder.add_edge("inspect_files", END)

        return graph_builder.compile()