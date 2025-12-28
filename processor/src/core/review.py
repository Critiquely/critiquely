# src/core/review.py
"""Deprecated: Use src.workflows.review.ReviewWorkflow instead.

This module provides backward compatibility for existing code that imports
run_review_graph from this location. New code should use the ReviewWorkflow
class directly.
"""

import logging
import warnings

from src.workflows.review import ReviewWorkflow

logger = logging.getLogger(__name__)


async def run_review_graph(
    repo_url: str, original_pr_url: str, base_branch: str, modified_files: str
):
    """Run the code review workflow.

    Deprecated:
        Use ReviewWorkflow.run() directly instead.

    Args:
        repo_url: URL of the repository to review.
        original_pr_url: URL of the PR that triggered the review.
        base_branch: Branch name to review.
        modified_files: JSON string of modified files.

    Returns:
        Result from the review workflow.
    """
    warnings.warn(
        "run_review_graph is deprecated. Use ReviewWorkflow.run() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    workflow = ReviewWorkflow()
    return await workflow.run(
        {
            "repo_url": repo_url,
            "original_pr_url": original_pr_url,
            "branch": base_branch,
            "modified_files": modified_files,
        }
    )
