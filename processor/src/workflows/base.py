"""Base workflow abstractions for Critiquely."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, TypeVar

from langgraph.graph import StateGraph

# TypeVar for workflow state - not bounded to TypedDict due to typing limitations
StateT = TypeVar("StateT")


@dataclass
class WorkflowMetadata:
    """Metadata about a workflow for registration and routing."""

    name: str
    """Unique identifier for the workflow (e.g., 'review', 'scan')."""

    display_name: str
    """Human-readable name (e.g., 'Code Review', 'Security Scan')."""

    queue_name: str
    """RabbitMQ queue name for this workflow."""

    supported_events: List[str]
    """GitHub events this workflow handles (e.g., ['pull_request.opened'])."""

    description: str
    """CLI help text describing the workflow."""

    required_message_fields: List[str] = field(default_factory=list)
    """Fields required in queue messages for validation."""


class BaseWorkflow(ABC, Generic[StateT]):
    """Abstract base class for all Critiquely workflows.

    Workflows encapsulate a LangGraph state machine that performs
    an agentic task. They can be invoked via CLI or queue consumer.

    Type Parameters:
        StateT: The TypedDict representing the workflow's state.
    """

    @classmethod
    @abstractmethod
    def metadata(cls) -> WorkflowMetadata:
        """Return workflow metadata for registration and routing.

        Returns:
            WorkflowMetadata describing this workflow.
        """
        ...

    @abstractmethod
    async def build_graph(self, **kwargs) -> StateGraph:
        """Build and return the LangGraph StateGraph.

        This method constructs the workflow's graph structure. It may
        use LangGraph primitives directly or higher-level builders
        like `create_deep_agent()` from the deepagents library.

        Args:
            **kwargs: Configuration options (e.g., llm_model, checkpointer).

        Returns:
            A compiled LangGraph StateGraph ready for invocation.
        """
        ...

    @abstractmethod
    def create_initial_state(self, message_data: Dict[str, Any]) -> StateT:
        """Create initial state from queue message or CLI input.

        Args:
            message_data: Dictionary containing workflow inputs.

        Returns:
            The initial state for graph execution.
        """
        ...

    @abstractmethod
    async def run(self, message_data: Dict[str, Any]) -> Any:
        """Execute the workflow with given input data.

        This is the main entry point for workflow execution.

        Args:
            message_data: Dictionary containing workflow inputs.

        Returns:
            Workflow result (structure depends on workflow type).
        """
        ...

    def validate_message(self, message_data: Dict[str, Any]) -> None:
        """Validate message has required fields.

        Args:
            message_data: Dictionary to validate.

        Raises:
            ValueError: If required fields are missing.
        """
        meta = self.metadata()
        missing = [
            field
            for field in meta.required_message_fields
            if field not in message_data
        ]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
