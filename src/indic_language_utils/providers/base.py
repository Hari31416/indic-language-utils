"""Provider declarations, lifecycle contracts, and explicit registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..errors import ConfigurationError
from ..languages import LanguageTag
from ..models import ProviderIdentity


class CapabilityId(StrEnum):
    TRANSLATION = "translation"
    TEXT_LANGUAGE_DETECTION = "text_language_detection"
    TRANSLITERATION = "transliteration"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


@dataclass(frozen=True, slots=True)
class CapabilityDeclaration:
    capability: CapabilityId
    languages: frozenset[LanguageTag] = frozenset()
    language_pairs: frozenset[tuple[LanguageTag, LanguageTag]] = frozenset()
    features: frozenset[str] = frozenset()
    limits: dict[str, int | float] = field(default_factory=dict)

    def supports(
        self,
        *,
        source: LanguageTag | None = None,
        target: LanguageTag | None = None,
        required_features: frozenset[str] = frozenset(),
    ) -> bool:
        if not required_features <= self.features:
            return False
        if source is not None and target is not None and self.language_pairs:
            return (source, target) in self.language_pairs
        requested = {tag for tag in (source, target) if tag is not None}
        return not self.languages or requested <= self.languages


@runtime_checkable
class Provider(Protocol):
    identity: ProviderIdentity
    capabilities: tuple[CapabilityDeclaration, ...]


@runtime_checkable
class AsyncLifecycle(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        name = provider.identity.provider
        if not name or name in self._providers:
            raise ConfigurationError(f"Provider registration is invalid: {name or '<empty>'}")
        capabilities = [item.capability for item in provider.capabilities]
        if len(capabilities) != len(set(capabilities)):
            raise ConfigurationError(f"Provider declares a capability more than once: {name}")
        self._providers[name] = provider

    def get(self, name: str) -> Provider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ConfigurationError(f"Provider is not registered: {name}") from exc

    def all(self) -> tuple[Provider, ...]:
        return tuple(self._providers.values())

    def declaration(self, provider: str, capability: CapabilityId) -> CapabilityDeclaration | None:
        return next(
            (item for item in self.get(provider).capabilities if item.capability == capability),
            None,
        )


class ResourceManager:
    """Starts resources in order and closes them in reverse order."""

    def __init__(self, *resources: AsyncLifecycle) -> None:
        self._resources = resources
        self._started: list[AsyncLifecycle] = []

    async def start(self) -> None:
        try:
            for resource in self._resources:
                await resource.start()
                self._started.append(resource)
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        error: BaseException | None = None
        while self._started:
            resource = self._started.pop()
            try:
                await resource.close()
            except BaseException as exc:
                error = error or exc
        if error is not None:
            raise error

    async def __aenter__(self) -> ResourceManager:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
