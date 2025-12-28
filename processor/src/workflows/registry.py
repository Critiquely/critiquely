"""Workflow registry for automatic discovery and routing."""

from typing import Dict, List, Optional, Type

from .base import BaseWorkflow, WorkflowMetadata


class WorkflowRegistry:
    """Singleton registry for all available workflows.

    Workflows register themselves using the @register_workflow decorator.
    The registry enables:
    - Looking up workflows by name for CLI dispatch
    - Finding workflows by event type for receiver routing
    - Mapping queue names to workflows for consumer dispatch
    """

    _workflows: Dict[str, Type[BaseWorkflow]] = {}

    @classmethod
    def register(cls, workflow_class: Type[BaseWorkflow]) -> Type[BaseWorkflow]:
        """Register a workflow class.

        Args:
            workflow_class: The workflow class to register.

        Returns:
            The same workflow class (for decorator use).

        Raises:
            ValueError: If a workflow with the same name is already registered.
        """
        meta = workflow_class.metadata()
        if meta.name in cls._workflows:
            raise ValueError(f"Workflow '{meta.name}' is already registered")
        cls._workflows[meta.name] = workflow_class
        return workflow_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseWorkflow]]:
        """Get a workflow class by name.

        Args:
            name: The workflow name (e.g., 'review').

        Returns:
            The workflow class, or None if not found.
        """
        return cls._workflows.get(name)

    @classmethod
    def get_for_event(cls, event_type: str) -> List[Type[BaseWorkflow]]:
        """Get all workflows that handle a specific GitHub event.

        Args:
            event_type: The GitHub event (e.g., 'pull_request.opened').

        Returns:
            List of workflow classes that handle this event.
        """
        return [
            wf
            for wf in cls._workflows.values()
            if event_type in wf.metadata().supported_events
        ]

    @classmethod
    def get_for_queue(cls, queue_name: str) -> Optional[Type[BaseWorkflow]]:
        """Get the workflow for a specific queue name.

        Args:
            queue_name: The RabbitMQ queue name.

        Returns:
            The workflow class, or None if not found.
        """
        for wf in cls._workflows.values():
            if wf.metadata().queue_name == queue_name:
                return wf
        return None

    @classmethod
    def all_workflows(cls) -> Dict[str, Type[BaseWorkflow]]:
        """Return all registered workflows.

        Returns:
            Dictionary mapping workflow names to classes.
        """
        return cls._workflows.copy()

    @classmethod
    def get_queue_mappings(cls) -> Dict[str, str]:
        """Return mapping of workflow names to queue names.

        Returns:
            Dictionary mapping workflow names to their queue names.
        """
        return {name: wf.metadata().queue_name for name, wf in cls._workflows.items()}

    @classmethod
    def clear(cls) -> None:
        """Clear all registered workflows (useful for testing)."""
        cls._workflows.clear()


def register_workflow(cls: Type[BaseWorkflow]) -> Type[BaseWorkflow]:
    """Decorator to register a workflow class.

    Usage:
        @register_workflow
        class MyWorkflow(BaseWorkflow[MyState]):
            ...

    Args:
        cls: The workflow class to register.

    Returns:
        The same workflow class.
    """
    return WorkflowRegistry.register(cls)
