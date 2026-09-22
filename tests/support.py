from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId


@dataclass
class FakeProvider:
    name: str
    capabilities: tuple[CapabilityDeclaration, ...]
    started: bool = False
    closed: bool = False
    calls: int = 0
    identity: ProviderIdentity = field(init=False)

    def __post_init__(self) -> None:
        self.identity = ProviderIdentity(self.name)

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def operation(self, gate: asyncio.Event | None = None) -> str:
        self.calls += 1
        if gate:
            await gate.wait()
        return "fake-result"


def declaration(capability: CapabilityId, **kwargs: object) -> CapabilityDeclaration:
    return CapabilityDeclaration(capability, **kwargs)  # type: ignore[arg-type]
