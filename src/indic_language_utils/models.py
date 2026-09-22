"""Shared immutable metadata. Capability request and result models live elsewhere."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    provider: str
    display_name: str | None = None
    unofficial: bool = False


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    model: str | None = None
    version: str | None = None
    service_id: str | None = None


@dataclass(frozen=True, slots=True)
class OperationContext:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionTiming:
    started_at: datetime
    finished_at: datetime
    provider_seconds: float | None = None
    queue_seconds: float | None = None

    @property
    def total_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    @classmethod
    def now(cls) -> ExecutionTiming:
        now = datetime.now(UTC)
        return cls(now, now)


@dataclass(frozen=True, slots=True)
class CacheMetadata:
    hit: bool
    backend: str
    key_version: int


@dataclass(frozen=True, slots=True)
class WarningInfo:
    code: str
    message: str


SharedModel = (
    ProviderIdentity
    | ModelIdentity
    | OperationContext
    | ExecutionTiming
    | CacheMetadata
    | WarningInfo
)


def model_to_dict(model: SharedModel) -> dict[str, Any]:
    """Serialize a shared dataclass. Secret values deliberately lack this route."""
    return asdict(model)
