from typing import Annotated, Optional
from typing_extensions import TypedDict
import operator
from langchain_core.messages import AnyMessage


# Focused state slices for better organization
class GitState(TypedDict):
    """Git-related state information"""
    repo_url: str
    clone_path: Optional[str]
    base_branch: str
    new_branch: Optional[str]


class ReviewState(TypedDict):
    """Code review state information"""
    modified_files: list[dict]
    current_recommendation: Optional[dict]
    recommendations: list[dict]
    # Tracking current file being processed
    active_file_name: Optional[str]
    active_file_content: Optional[str]
    active_file_lines_changed: Optional[str]
    updated_files: Annotated[list[str], operator.add]  # Files modified by MCP tools


class PRState(TypedDict):
    """Pull request state information"""
    original_pr_url: str
    pr_number: Optional[str]
    pr_url: Optional[str]


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
    modified_files: list[dict]

    # Recommendation Details
    current_recommendation: Optional[dict]
    recommendations: list[dict]
    file_recommendations: Optional[list[dict]]  # Recommendations for a specific file
    target_file: Optional[str]  # Target file path for grouped recommendations

    # PR Details
    original_pr_url: str
    pr_number: Optional[str]
    pr_url: Optional[str]

    # Tracking Information - Used during bot execution
    active_file_name: Optional[str]
    active_file_content: Optional[str]
    active_file_lines_changed: Optional[str]
    updated_files: Annotated[list[str], operator.add]  # Files modified by MCP tools


# Utility functions to work with state slices
def extract_git_state(state: DevAgentState) -> GitState:
    """Extract git-related state"""
    return {
        'repo_url': state['repo_url'],
        'clone_path': state.get('clone_path'),
        'base_branch': state['base_branch'],
        'new_branch': state.get('new_branch'),
    }


def extract_review_state(state: DevAgentState) -> ReviewState:
    """Extract review-related state"""
    return {
        'modified_files': state.get('modified_files', []),
        'current_recommendation': state.get('current_recommendation'),
        'recommendations': state.get('recommendations', []),
        'active_file_name': state.get('active_file_name'),
        'active_file_content': state.get('active_file_content'),
        'active_file_lines_changed': state.get('active_file_lines_changed'),
        'updated_files': state.get('updated_files', []),
    }


def extract_pr_state(state: DevAgentState) -> PRState:
    """Extract PR-related state"""
    return {
        'original_pr_url': state['original_pr_url'],
        'pr_number': state.get('pr_number'),
        'pr_url': state.get('pr_url'),
    }
