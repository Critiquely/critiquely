import os
import uuid
import operator
import wikipedia
from typing import Annotated, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from IPython.display import display, Image

from langchain_core.messages import (
    AnyMessage, HumanMessage, ToolMessage
)
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langgraph.graph import (
    StateGraph, START, END, MessagesState
)
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# --- Constants ---
DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"

# --- LangGraph State ---
class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

# --- Wikipedia Tool ---
def get_wiki_data(topic: str) -> str:
    return wikipedia.summary(topic)

class WikipediaTopic(BaseModel):
    topic: str = Field(description="The Wikipedia article topic to search")

@tool(args_schema=WikipediaTopic)
def wikipedia_search(topic: str) -> str:
    """Returns the summary of the Wikipedia page for the given topic."""
    return get_wiki_data(topic)

# --- Tool Execution Logic ---
tools = [wikipedia_search]
tools_names = {t.name: t for t in tools}

def tool_exists(state: State) -> bool:
    return bool(state['messages'][-1].tool_calls)

def execute_tools(state: State) -> dict:
    tool_calls = state['messages'][-1].tool_calls
    results = []

    for t in tool_calls:
        tool_name = t['name']
        if tool_name not in tools_names:
            result = "Error: No such tool exists. Please try again."
        else:
            result = tools_names[tool_name].invoke(t['args'])

        results.append(
            ToolMessage(
                tool_call_id=t['id'],
                name=tool_name,
                content=str(result)
            )
        )

    return {'messages': results}

# --- LLM Logic ---
model = init_chat_model(DEFAULT_MODEL).bind_tools(tools)

def run_llm(state: State) -> dict:
    response = model.invoke(state['messages'])
    return {'messages': [response]}

# --- Graph Definition ---
graph_builder = StateGraph(State)
graph_builder.add_node("llm", run_llm)
graph_builder.add_node("tools", execute_tools)
graph_builder.add_conditional_edges("llm", tool_exists, {True: "tools", False: END})
graph_builder.add_edge("tools", "llm")
graph_builder.set_entry_point("llm")
graph = graph_builder.compile()

# --- Streaming Output ---
def print_stream(stream):
    for s in stream:
        print("TEST HERE", s)
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()

# --- Example Usage ---
if __name__ == "__main__":
    messages = [HumanMessage(content="Give me the latest research paper on attention is all you need")]
    result = graph.invoke({"messages": messages})
    print_stream(graph.stream({"messages": messages}, stream_mode="values"))
