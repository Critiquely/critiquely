from typing_extensions import TypedDict
from typing import Annotated, Optional
import operator
from langchain_core.messages import AnyMessage

class DevAgentState(TypedDict):
    """
    Shared state passed between LangGraph nodes during DevAgent execution.
    Combines all focused state slices for backward compatibility.
    """
    messages: Annotated[list[AnyMessage], operator.add]

    # Repository details
    repo_url: str
    base_branch: str
    new_branch: Optional[str]

    # File Details
    clone_path: Optional[str]
    # modified_files: list[dict]

    # # Recommendation Details
    # current_recommendation: Optional[dict]
    # recommendations: list[dict]

    # # PR Details
    # original_pr_url: str
    # pr_number: Optional[str]
    # pr_url: Optional[str]

    # # Tracking Information - Used during bot execution
    # active_file_name: Optional[str]
    # active_file_content: Optional[str]
    # active_file_lines_changed: Optional[str]
    # updated_files: list[str]  # Files modified by MCP tools