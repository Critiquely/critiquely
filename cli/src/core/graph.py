
from langgraph.graph import StateGraph, END

from src.core.nodes import clone_repo, inspect_files
from src.core.state import DevAgentState

def build_graph():
    graph_builder = StateGraph(DevAgentState)
    graph_builder.add_node("clone_repo", clone_repo)
    graph_builder.add_node("inspect_files", inspect_files)

    graph_builder.set_entry_point("clone_repo")
    graph_builder.add_edge("clone_repo", "inspect_files")
    graph_builder.add_edge("inspect_files", END)

    return graph_builder.compile()