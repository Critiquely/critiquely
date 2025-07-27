import logging

from langgraph.graph import END, StateGraph
from src.core.state import DevAgentState

logger = logging.getLogger(__name__)


def has_more_files_to_inspect(state: DevAgentState) -> str:
    """Keep inspecting until the modified-file list is empty."""
    remaining = state.get("modified_files", [])

    if remaining:
        next_file = remaining[0].get("filename", "<unknown>")
        logger.info(
            f"🔄 {len(remaining)} file(s) left to inspect; next up: {next_file}"
        )
        return "inspect_files"

    logger.info("✅ All modified files processed; exiting inspect loop")
    return END


def has_tool_invocation(state: DevAgentState):
    """
    Route to the ToolNode if the last message has tool calls; otherwise END.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        error = f"No messages found to route: {state}"
        logger.error(f"❌ {error}")
        raise ValueError(error)

    has_tools = bool(getattr(ai_message, "tool_calls", None))

    if has_tools:
        tool_name = ai_message.tool_calls[0]["name"]
        logger.info(f"🚀 Routing to tool: {tool_name}")
        return "tools"

    logger.info("🏁 Routing to END node")
    return END
