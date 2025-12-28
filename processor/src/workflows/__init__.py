"""Workflow framework for Critiquely agentic workflows."""

from .base import BaseWorkflow, WorkflowMetadata
from .registry import WorkflowRegistry, register_workflow

# Import workflows to trigger registration
from .review import ReviewWorkflow

__all__ = [
    "BaseWorkflow",
    "WorkflowMetadata",
    "WorkflowRegistry",
    "register_workflow",
    "ReviewWorkflow",
]
