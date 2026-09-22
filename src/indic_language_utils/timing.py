"""Operation timing helpers with an injectable monotonic clock."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .models import ExecutionTiming


@dataclass(slots=True)
class Timer:
    clock: Callable[[], float] = time.monotonic
    _started_monotonic: float = field(init=False)
    _started_at: datetime = field(init=False)

    def __post_init__(self) -> None:
        self._started_monotonic = self.clock()
        self._started_at = datetime.now(UTC)

    def finish(
        self, *, provider_seconds: float | None = None, queue_seconds: float | None = None
    ) -> ExecutionTiming:
        elapsed = self.clock() - self._started_monotonic
        return ExecutionTiming(
            started_at=self._started_at,
            finished_at=self._started_at + timedelta(seconds=elapsed),
            provider_seconds=provider_seconds,
            queue_seconds=queue_seconds,
        )
