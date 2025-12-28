"""Review-specific nodes for the code review workflow.

This module contains nodes that are specific to the code review workflow,
particularly the LLM-driven inspection and recommendation application.
"""

import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from .state import ReviewState

logger = logging.getLogger(__name__)


def strip_markdown_json(content: str) -> str:
    """Strip markdown code block formatting from JSON responses.

    Handles cases where the LLM wraps JSON in markdown code blocks like:
    ```json
    {...}
    ```

    Args:
        content: The raw response content that may contain markdown formatting.

    Returns:
        The cleaned JSON string.
    """
    content = content.strip()

    if content.startswith("```"):
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline + 1 :]

        if content.endswith("```"):
            content = content[:-3].rstrip()

    return content.strip()


def inspect_files(llm, state: ReviewState) -> dict:
    """Inspect modified files and generate review recommendations.

    This node sends each modified file to the LLM for review,
    collecting recommendations for code improvements.

    Args:
        llm: The LLM instance to use for review.
        state: Current workflow state.

    Returns:
        Updated state with recommendations.
    """
    if not state.get("modified_files"):
        logger.info("No modified files to inspect. Skipping.")
        return state

    entry = state["modified_files"].pop(0)
    fname = entry.get("filename")
    fpath = Path(state.get("clone_path", "")) / fname

    try:
        file_text = fpath.read_text(encoding="utf-8")
    except Exception as e:
        msg = f"Could not read file {fpath}: {e}"
        logger.error(msg)
        state.setdefault("messages", []).append(HumanMessage(content=msg))
        return state

    lines_changed = entry.get("lines_changed", [])
    logger.info(f"Inspecting {fname} (lines {lines_changed})")

    state.update(
        {
            "active_file_name": fname,
            "active_file_content": file_text,
            "active_file_lines_changed": lines_changed,
        }
    )

    prompt = HumanMessage(
        content=(
            "You are a senior Python reviewer.\n\n"
            f"File: {fpath}\n"
            f"Modified lines: {lines_changed}\n\n"
            "Review only sections directly impacted by the modifications. "
            "Provide up to 3 high-impact recommendations in JSON array only.\n\n"
            "Output format:\n"
            "[{'file':'<filename>','summary':'<github commit style summary using "
            "conventional commit syntax>','recommendation':'<recommendation>'}]\n\n"
            "You can have multiple objects for a specific file if there are "
            "multiple recommendations.\n\n"
            "**DO NOT** include anything other than the JSON list\n\n"
            f"File contents:\n{file_text}"
        )
    )
    state.setdefault("messages", []).append(prompt)
    logger.info("Sending review prompt to LLM")
    response = llm.invoke([prompt])
    logger.info("LLM response received")
    state["messages"].append(response)

    try:
        cleaned_content = strip_markdown_json(response.content)
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        msg = f"Failed to parse JSON: {e}"
        logger.error(msg)
        parsed = []

    state.setdefault("recommendations", []).extend(parsed)
    return state


def apply_recommendations_with_mcp(llm_with_tools, state: ReviewState) -> ReviewState:
    """Apply recommendations using MCP tools.

    This node takes each recommendation and uses the LLM with MCP tools
    to apply the suggested changes to the codebase.

    Args:
        llm_with_tools: LLM instance bound with MCP tools.
        state: Current workflow state.

    Returns:
        Updated state after applying recommendation.
    """
    recs_list = state.get("recommendations", [])
    if not recs_list:
        logger.info("No recommendations to apply. Skipping.")
        return state

    current = recs_list.pop(0)
    state.update({"current_recommendation": current})
    file_path = Path(current.get("file", ""))
    recs = current.get("recommendation")

    if not recs:
        logger.warning(f"No recommendations for {file_path}")
        return state
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return state

    file_text = file_path.read_text(encoding="utf-8")
    logger.info(f"Applying recommendation to {file_path.name}")

    instructions = "\n".join(f"- {r}" for r in recs) if isinstance(recs, list) else recs
    prompt = HumanMessage(
        content=(
            "You are a coding assistant. A user requested edits to a source file.\n\n"
            f"File path: {file_path}\n\n"
            f"File contents:\n{file_text}\n\n"
            f"Requested changes:\n{instructions}\n\n"
            "Choose and invoke a tool from your toolkit. Return only the invocation."
        )
    )
    state.setdefault("messages", []).append(prompt)
    logger.info("Invoking LLM with tools")

    result = llm_with_tools.invoke([prompt])
    logger.info("Received tool invocation from LLM")
    state["messages"].append(result)

    state.setdefault("updated_files", []).append(str(file_path))
    logger.info(
        f"Applied recommendations to {file_path.name}; {len(recs_list)} remaining"
    )
    return state
