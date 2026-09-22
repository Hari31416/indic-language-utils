"""Reusable concurrency limits keyed by provider and capability."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from .providers import CapabilityId


class ConcurrencyLimiter:
    def __init__(
        self, default_limit: int, limits: dict[tuple[str, CapabilityId], int] | None = None
    ) -> None:
        if default_limit < 1 or any(value < 1 for value in (limits or {}).values()):
            raise ValueError("Concurrency limits must be positive")
        self._default = default_limit
        self._limits = limits or {}
        self._semaphores: dict[tuple[str, CapabilityId], asyncio.Semaphore] = {}

    @asynccontextmanager
    async def slot(self, provider: str, capability: CapabilityId) -> AsyncIterator[None]:
        key = (provider, capability)
        semaphore = self._semaphores.get(key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._limits.get(key, self._default))
            self._semaphores[key] = semaphore
        async with semaphore:
            yield
