"""Reusable provider contract checks for built-in and external adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from indic_language_utils.providers import AsyncLifecycle, Provider


def assert_valid_declaration(provider: Provider) -> None:
    assert provider.identity.provider
    capabilities = [item.capability for item in provider.capabilities]
    assert len(capabilities) == len(set(capabilities))
    for declaration in provider.capabilities:
        assert all(value >= 0 for value in declaration.limits.values())


async def assert_lifecycle(
    resource: AsyncLifecycle, is_started: Callable[[], bool], is_closed: Callable[[], bool]
) -> None:
    await resource.start()
    assert is_started()
    await resource.close()
    assert is_closed()


async def assert_cancellation(operation: Callable[[], Awaitable[object]]) -> None:
    async def invoke() -> object:
        return await operation()

    task: asyncio.Task[object] = asyncio.create_task(invoke())
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return
    raise AssertionError("Provider swallowed cancellation")
