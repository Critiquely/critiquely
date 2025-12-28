"""Event routing rules for GitHub webhooks.

This module defines how GitHub events are routed to workflow queues.
Each routing rule maps an event type to a queue and provides a
message builder function to transform the webhook payload.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class GitHubEventType(str, Enum):
    """GitHub webhook event types."""

    PULL_REQUEST_OPENED = "pull_request.opened"
    PULL_REQUEST_SYNCHRONIZE = "pull_request.synchronize"
    PULL_REQUEST_CLOSED = "pull_request.closed"
    PULL_REQUEST_REOPENED = "pull_request.reopened"
    PUSH = "push"
    ISSUES_OPENED = "issues.opened"
    ISSUES_LABELED = "issues.labeled"
    ISSUE_COMMENT_CREATED = "issue_comment.created"


@dataclass
class RoutingRule:
    """Defines how an event maps to a workflow queue."""

    event_type: GitHubEventType
    """The GitHub event type this rule handles."""

    queue_name: str
    """The RabbitMQ queue to publish to."""

    workflow_name: str
    """The workflow name (for logging/debugging)."""

    message_builder: Callable[[Dict[str, Any]], Dict[str, Any]]
    """Function to build the queue message from webhook payload."""

    filter_condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    """Optional filter to conditionally apply this rule."""


class EventRouter:
    """Routes GitHub events to appropriate workflow queues."""

    def __init__(self):
        self._rules: List[RoutingRule] = []

    def register_rule(self, rule: RoutingRule) -> None:
        """Register a routing rule.

        Args:
            rule: The routing rule to register.
        """
        self._rules.append(rule)

    def get_routes(
        self, event_type: str, payload: Dict[str, Any]
    ) -> List[RoutingRule]:
        """Get all applicable routes for an event.

        Args:
            event_type: The full GitHub event type (e.g., 'pull_request.opened').
            payload: The webhook payload.

        Returns:
            List of applicable routing rules.
        """
        return [
            rule
            for rule in self._rules
            if rule.event_type.value == event_type
            and (rule.filter_condition is None or rule.filter_condition(payload))
        ]

    @property
    def registered_events(self) -> List[str]:
        """Get list of all registered event types."""
        return list(set(rule.event_type.value for rule in self._rules))


def build_review_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build review workflow message from PR event payload.

    Args:
        payload: GitHub webhook payload.

    Returns:
        Message dict for the review queue.
    """
    pr_data = payload["pull_request"]
    repo_data = payload["repository"]
    return {
        "repo_url": repo_data.get("clone_url"),
        "original_pr_url": pr_data.get("html_url"),
        "branch": pr_data.get("head", {}).get("ref"),
        "modified_files": [],  # Will be populated by handler
        "workflow": "review",
    }


def create_default_router() -> EventRouter:
    """Create router with default routing rules.

    Returns:
        EventRouter configured with standard rules.
    """
    router = EventRouter()

    # Review workflow on PR opened
    router.register_rule(
        RoutingRule(
            event_type=GitHubEventType.PULL_REQUEST_OPENED,
            queue_name="code_review_queue",
            workflow_name="review",
            message_builder=build_review_message,
        )
    )

    # Review workflow on PR synchronized (new commits pushed)
    router.register_rule(
        RoutingRule(
            event_type=GitHubEventType.PULL_REQUEST_SYNCHRONIZE,
            queue_name="code_review_queue",
            workflow_name="review",
            message_builder=build_review_message,
        )
    )

    # Future: Add more routing rules here
    # Example: Security scan on push to main
    # router.register_rule(RoutingRule(
    #     event_type=GitHubEventType.PUSH,
    #     queue_name="security_scan_queue",
    #     workflow_name="scan",
    #     message_builder=build_scan_message,
    #     filter_condition=lambda p: p.get("ref") == "refs/heads/main",
    # ))

    return router
