"""Provider-neutral lifecycle, capability, auth, execution, and cost contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable


class ProviderKind(str, Enum):
    LOCAL = "local"
    EXTERNAL_API = "external_api"
    ADEPT_CLOUD = "adept_cloud"


class ProviderState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"


class ExecutionState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CostOwnership(str, Enum):
    """Account or resource owner responsible for execution cost."""

    LOCAL_RESOURCES = "local_resources"
    CUSTOMER_PROVIDER_ACCOUNT = "customer_provider_account"
    ADEPT_CLOUD_ACCOUNT = "adept_cloud_account"
    NO_MONETARY_CHARGE = "no_monetary_charge"


@dataclass(frozen=True)
class ProviderCapability:
    """A discoverable provider feature and its non-secret constraints."""

    name: str
    version: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthenticationRequest:
    """Provider-neutral authentication material."""

    credentials: Mapping[str, str] = field(default_factory=dict)
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthenticationResult:
    authenticated: bool
    principal: str | None = None
    expires_at: str | None = None
    message: str = ""


@dataclass(frozen=True)
class ProviderExecutionRequest:
    """Provider-neutral request; workflow-specific data remains opaque."""

    request_id: str
    capability: str
    workflow_key: str
    inputs: Mapping[str, Any]
    options: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ExecutionHandle:
    provider_kind: ProviderKind
    execution_id: str
    submitted_at: str


@dataclass(frozen=True)
class ExecutionStatus:
    handle: ExecutionHandle
    state: ExecutionState
    progress: float | None = None
    message: str = ""
    updated_at: str | None = None


@dataclass(frozen=True)
class CostEstimate:
    ownership: CostOwnership
    amount: str | None = None
    currency: str | None = None
    billable_units: Mapping[str, str] = field(default_factory=dict)
    estimate_id: str | None = None


@dataclass(frozen=True)
class CostReceipt:
    ownership: CostOwnership
    amount: str | None = None
    currency: str | None = None
    billable_units: Mapping[str, str] = field(default_factory=dict)
    provider_receipt_id: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    handle: ExecutionHandle
    outputs: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    cost: CostReceipt | None = None


@runtime_checkable
class CapabilityProvider(Protocol):
    kind: ProviderKind

    async def capabilities(self) -> tuple[ProviderCapability, ...]: ...


@runtime_checkable
class AuthenticatingProvider(Protocol):
    async def authenticate(
        self, request: AuthenticationRequest
    ) -> AuthenticationResult: ...

    async def clear_authentication(self) -> None: ...


@runtime_checkable
class LifecycleProvider(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def state(self) -> ProviderState: ...


@runtime_checkable
class ExecutionProvider(Protocol):
    async def estimate_cost(
        self, request: ProviderExecutionRequest
    ) -> CostEstimate: ...

    async def submit(
        self, request: ProviderExecutionRequest
    ) -> ExecutionHandle: ...

    async def execution_status(
        self, handle: ExecutionHandle
    ) -> ExecutionStatus: ...

    async def cancel(self, handle: ExecutionHandle) -> ExecutionStatus: ...

    async def retrieve(self, handle: ExecutionHandle) -> ExecutionResult: ...


class LocalProvider(
    CapabilityProvider,
    AuthenticatingProvider,
    LifecycleProvider,
    ExecutionProvider,
    Protocol,
):
    """Contract for machine-local generation infrastructure."""


class ExternalApiProvider(
    CapabilityProvider,
    AuthenticatingProvider,
    LifecycleProvider,
    ExecutionProvider,
    Protocol,
):
    """Contract for third-party remote APIs."""


class AdeptCloudProvider(
    CapabilityProvider,
    AuthenticatingProvider,
    LifecycleProvider,
    ExecutionProvider,
    Protocol,
):
    """Contract for first-party Adept Cloud services."""
