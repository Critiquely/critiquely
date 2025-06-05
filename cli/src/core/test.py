from typing import Annotated
import os

from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages

from IPython.display import Image, display
from pathlib import Path
from PIL import Image

os.environ["ANTHROPIC_API_KEY"] = "sk-..."

llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)

def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", chatbot)

graph_builder.add_edge(START, "chatbot")

graph = graph_builder.compile()

try:
    img = graph.get_graph().draw_mermaid_png()
    output_path = Path("graph.png")
    with open(output_path, "wb") as f:
        f.write(img)
    print(f"Saved image to {output_path}")
except Exception as e:
    print(f"Could not generate image: {e}")