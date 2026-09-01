from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class WorkflowStartRequest:
    workflow_type: str
    business_key: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


@dataclass(frozen=True)
class WorkflowHandle:
    workflow_id: str
    workflow_type: str
    business_key: str


class WorkflowPort(Protocol):
    """Boundary for long-running business orchestration.

    Implementations may use Temporal, Camunda, or another engine. BoutiqueOS domain
    services must not depend directly on a workflow vendor SDK.
    """

    def start(self, request: WorkflowStartRequest) -> WorkflowHandle: ...

    def signal(self, workflow_id: str, signal_name: str, payload: dict[str, Any] | None = None) -> None: ...

    def cancel(self, workflow_id: str, reason: str | None = None) -> None: ...
