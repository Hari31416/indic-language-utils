"""Deterministic provider selection from explicit ordered routes."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import UnsupportedCapabilityError, UnsupportedLanguageError
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


class OrderedRouter:
    def __init__(
        self, registry: ProviderRegistry, routes: dict[CapabilityId, tuple[str, ...]]
    ) -> None:
        self._registry = registry
        self._routes = routes

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
            return tuple(matches)
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
