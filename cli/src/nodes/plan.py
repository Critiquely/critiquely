import os
from langchain.chat_models import init_chat_model

os.environ["ANTHROPIC_API_KEY"] = "sk-..."

llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

def plan(state: State):
    return {"messages": [llm.invoke(state["messages"])]}