"""Code review workflow implementation."""

import json
import logging
from typing import Any, Dict
from uuid import uuid4

from src.workflows.base import BaseWorkflow, WorkflowMetadata
from src.workflows.registry import register_workflow

from .graph import build_review_graph
from .state import ReviewState

logger = logging.getLogger(__name__)


@register_workflow
class ReviewWorkflow(BaseWorkflow[ReviewState]):
    """Code review workflow that creates improvement PRs.

    This workflow analyzes pull requests, generates code improvement
    recommendations, and creates a new PR with the suggested changes.
    """

    @classmethod
    def metadata(cls) -> WorkflowMetadata:
        """Return metadata for the review workflow."""
        return WorkflowMetadata(
            name="review",
            display_name="Code Review",
            queue_name="code_review_queue",
            supported_events=["pull_request.opened", "pull_request.synchronize"],
            description="Perform automated code review and create improvement PR",
            required_message_fields=[
                "repo_url",
                "original_pr_url",
                "branch",
                "modified_files",
            ],
        )

    async def build_graph(self, **kwargs):
        """Build the review workflow graph."""
        return await build_review_graph(
            llm_model=kwargs.get("llm_model", "claude-sonnet-4-5-20250929"),
            checkpointer=kwargs.get("checkpointer"),
        )

    def create_initial_state(self, message_data: Dict[str, Any]) -> ReviewState:
        """Create initial state from queue message or CLI input.

        Args:
            message_data: Dictionary containing repo_url, original_pr_url,
                         branch, and modified_files.

        Returns:
            Initial ReviewState for graph execution.
        """
        modified_files = message_data["modified_files"]
        if isinstance(modified_files, str):
            modified_files = json.loads(modified_files)

        return ReviewState(
            repo_url=message_data["repo_url"],
            original_pr_url=message_data["original_pr_url"],
            base_branch=message_data["branch"],
            modified_files=modified_files,
            messages=[],
            clone_path=None,
            new_branch=None,
            current_recommendation=None,
            recommendations=[],
            pr_number=None,
            pr_url=None,
            active_file_name=None,
            active_file_content=None,
            active_file_lines_changed=None,
            updated_files=[],
        )

    async def run(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the review workflow.

        Args:
            message_data: Dictionary containing workflow inputs.

        Returns:
            Result dictionary with status and PR URL.
        """
        self.validate_message(message_data)

        logger.info(f"Starting review for {message_data.get('original_pr_url')}")

        graph = await self.build_graph()
        initial_state = self.create_initial_state(message_data)
        config = {"configurable": {"thread_id": str(uuid4())}}

        # Accumulate state from partial updates
        accumulated_state = dict(initial_state)
        async for event in graph.astream(initial_state, config):
            for value in event.values():
                # Merge partial state updates into accumulated state
                for key, val in value.items():
                    if val is not None:  # Only update non-None values
                        accumulated_state[key] = val
                if messages := value.get("messages"):
                    logger.info(f"Assistant: {messages[-1].content}")

        return {
            "status": "completed",
            "pr_url": accumulated_state.get("pr_url"),
            "pr_number": accumulated_state.get("pr_number"),
        }
