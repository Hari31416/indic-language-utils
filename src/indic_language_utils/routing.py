"""Deterministic provider selection from explicit ordered routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .errors import ConfigurationError, UnsupportedCapabilityError, UnsupportedLanguageError
from .languages import LanguageTag
from .providers import CapabilityDeclaration, CapabilityId, Provider, ProviderRegistry


@dataclass(frozen=True, slots=True)
class RouteRequirement:
    capability: CapabilityId
    source: LanguageTag | None = None
    target: LanguageTag | None = None
    features: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    provider: Provider
    declaration: CapabilityDeclaration


class RouteSelector(Protocol):
    """Choose an ordered subset of eligible providers for one request."""

    def __call__(
        self, requirement: RouteRequirement, candidates: tuple[RouteCandidate, ...]
    ) -> tuple[RouteCandidate, ...]: ...


class OrderedRouter:
    def __init__(
        self,
        registry: ProviderRegistry,
        routes: dict[CapabilityId, tuple[str, ...]],
        *,
        selector: RouteSelector | None = None,
    ) -> None:
        self._registry = registry
        self._routes = routes
        self._selector = selector

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

    def candidates(self, requirement: RouteRequirement) -> tuple[RouteCandidate, ...]:
        names = self._routes.get(requirement.capability)
        if not names:
            raise UnsupportedCapabilityError(
                "No route is configured for the requested capability",
                capability=requirement.capability.value,
            )
        declared = False
        matches: list[RouteCandidate] = []
        for name in names:
            declaration = self._registry.declaration(name, requirement.capability)
            if declaration is None:
                continue
            declared = True
            if declaration.supports(
                source=requirement.source,
                target=requirement.target,
                required_features=requirement.features,
            ):
                matches.append(RouteCandidate(self._registry.get(name), declaration))
        if matches:
            eligible = tuple(matches)
            if self._selector is None:
                return eligible
            selected = self._selector(requirement, eligible)
            eligible_ids = {id(item) for item in eligible}
            selected_ids = [item.provider.identity.provider for item in selected]
            if len(selected_ids) != len(set(selected_ids)) or any(
                id(item) not in eligible_ids for item in selected
            ):
                raise ConfigurationError(
                    "Route selector returned an ineligible or duplicate provider"
                )
            if not selected:
                raise UnsupportedCapabilityError(
                    "Route selector excluded every eligible provider",
                    capability=requirement.capability.value,
                )
            return tuple(selected)
        if declared:
            raise UnsupportedLanguageError(
                "No configured provider satisfies the language or feature requirements",
                capability=requirement.capability.value,
            )
        raise UnsupportedCapabilityError(
            "Configured providers do not declare the requested capability",
            capability=requirement.capability.value,
        )

    def select(self, requirement: RouteRequirement) -> RouteCandidate:
        return self.candidates(requirement)[0]
