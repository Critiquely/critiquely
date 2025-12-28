"""Routing functions for the review workflow graph."""

import logging

from langgraph.graph import END

from .state import ReviewState

logger = logging.getLogger(__name__)


def has_more_files_to_inspect(state: ReviewState) -> str:
    """Determine if there are more files to inspect.

    Routes back to inspect_files if files remain, otherwise to END.

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    remaining = state.get("modified_files", [])

    if remaining:
        next_file = remaining[0].get("filename", "<unknown>")
        logger.info(f"{len(remaining)} file(s) left to inspect; next up: {next_file}")
        return "inspect_files"

    logger.info("All modified files processed; exiting inspect loop")
    return END


def has_tool_invocation(state: ReviewState) -> str:
    """Determine if the LLM requested a tool call.

    Routes to tools node if tool calls exist, otherwise to END.

    Args:
        state: Current workflow state.

    Returns:
        'tools' if tool calls exist, END otherwise.

    Raises:
        ValueError: If no messages found in state.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        error = f"No messages found to route: {state}"
        logger.error(error)
        raise ValueError(error)

    has_tools = bool(getattr(ai_message, "tool_calls", None))

    if has_tools:
        tool_name = ai_message.tool_calls[0]["name"]
        logger.info(f"Routing to tool: {tool_name}")
        return "tools"

    logger.info("Routing to END node")
    return END
