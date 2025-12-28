"""State definitions for the code review workflow."""

from typing import Annotated, Optional

import operator
from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict


class ReviewState(TypedDict):
    """State for the code review workflow.

    This TypedDict defines all state fields passed between nodes
    during review graph execution.
    """

    # LangGraph message accumulator (append-only)
    messages: Annotated[list[AnyMessage], operator.add]

    # Repository details
    repo_url: str
    base_branch: str
    new_branch: Optional[str]

    # File details
    clone_path: Optional[str]
    modified_files: list[dict]

    # Recommendation details
    current_recommendation: Optional[dict]
    recommendations: list[dict]

    # PR details
    original_pr_url: str
    pr_number: Optional[str]
    pr_url: Optional[str]

    # Tracking information - used during bot execution
    active_file_name: Optional[str]
    active_file_content: Optional[str]
    active_file_lines_changed: Optional[str]
    updated_files: list[str]
