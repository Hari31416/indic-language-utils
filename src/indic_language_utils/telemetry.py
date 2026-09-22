"""Small telemetry protocols and safe standard-library logging."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Protocol

SAFE_FIELDS = frozenset(
    {
        "event",
        "capability",
        "provider",
        "model",
        "source_language",
        "target_language",
        "outcome",
        "cache_level",
        "fallback_count",
        "attempt_count",
        "request_id",
        "duration_seconds",
    }
)


class EventLogger(Protocol):
    def emit(self, event: str, fields: Mapping[str, object]) -> None: ...


class MetricHook(Protocol):
    def increment(self, name: str, value: float, attributes: Mapping[str, str]) -> None: ...

    def observe(self, name: str, value: float, attributes: Mapping[str, str]) -> None: ...


class TraceHook(Protocol):
    def span(self, name: str, attributes: Mapping[str, str]) -> AbstractContextManager[object]: ...


class StandardEventLogger:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("indic_language_utils")

    def emit(self, event: str, fields: Mapping[str, object]) -> None:
        safe = {key: value for key, value in fields.items() if key in SAFE_FIELDS}
        safe["event"] = event
        self._logger.info(event, extra={"language_utils": safe})


class NoOpMetrics:
    def increment(self, name: str, value: float, attributes: Mapping[str, str]) -> None:
        return None

    def observe(self, name: str, value: float, attributes: Mapping[str, str]) -> None:
        return None


class NoOpTracing:
    def span(self, name: str, attributes: Mapping[str, str]) -> AbstractContextManager[object]:
        return nullcontext()
