"""Provider contract checks for adapter authors and application test suites."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from .languages import LanguageTag
from .providers import AsyncLifecycle, CapabilityId, Provider

T = TypeVar("T")


def assert_valid_declaration(provider: Provider, capability: CapabilityId | None = None) -> None:
    """Check identity, capability uniqueness, and declared limits."""
    assert provider.identity.provider, "Provider ID must be non-empty"
    capabilities = [item.capability for item in provider.capabilities]
    assert len(capabilities) == len(set(capabilities)), "Capabilities must be unique"
    if capability is not None:
        assert capability in capabilities, f"Provider does not declare {capability.value}"
    for declaration in provider.capabilities:
        assert all(value >= 0 for value in declaration.limits.values()), "Limits cannot be negative"


def assert_batch_output(
    outputs: Sequence[T], expected_count: int, *, valid_item: Callable[[T], bool]
) -> None:
    """Check that a provider returns one valid output per input in a batch."""
    assert len(outputs) == expected_count, "Provider returned the wrong number of outputs"
    assert all(valid_item(item) for item in outputs), "Provider returned an invalid output"


def assert_declared_support(
    provider: Provider,
    capability: CapabilityId,
    *,
    source: LanguageTag | None = None,
    target: LanguageTag | None = None,
    expected: bool = True,
) -> None:
    """Check that advertised language coverage matches the adapter's contract."""
    declaration = next(
        (item for item in provider.capabilities if item.capability == capability), None
    )
    assert declaration is not None, f"Provider does not declare {capability.value}"
    assert declaration.supports(source=source, target=target) == expected, (
        "Provider language declaration does not match expected support"
    )


def assert_fallback_result(result: object, *, provider_id: str, fallback_count: int = 1) -> None:
    """Check the selected provider and fallback count on any capability result."""
    provider = getattr(result, "provider", None)
    actual_id = provider if isinstance(provider, str) else getattr(provider, "provider", None)
    assert actual_id == provider_id, f"Expected provider {provider_id}, got {actual_id}"
    assert getattr(result, "fallback_count", None) == fallback_count, "Unexpected fallback count"


async def assert_lifecycle(
    resource: AsyncLifecycle,
    is_started: Callable[[], bool],
    is_closed: Callable[[], bool],
) -> None:
    """Check start and close, including cleanup when a check fails."""
    await resource.start()
    try:
        assert is_started(), "Provider did not start"
    finally:
        await resource.close()
    assert is_closed(), "Provider did not close"


async def assert_cancellation(
    operation: Callable[[], Awaitable[object]],
    *,
    started: asyncio.Event | None = None,
    timeout_seconds: float = 1.0,
) -> None:
    """Cancel an in-flight operation and check that cancellation propagates."""

    async def invoke() -> object:
        return await operation()

    task = asyncio.create_task(invoke())
    try:
        if started is not None:
            await asyncio.wait_for(started.wait(), timeout_seconds)
        else:
            await asyncio.sleep(0)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout_seconds)
        except asyncio.CancelledError:
            return
        raise AssertionError("Provider swallowed cancellation")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
