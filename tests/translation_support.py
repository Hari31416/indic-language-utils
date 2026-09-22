from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from indic_language_utils.errors import OutputValidationError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.processors import ProcessorIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId, ProviderRegistry
from indic_language_utils.routing import OrderedRouter
from indic_language_utils.translation.models import (
    ProviderTranslationResult,
    TranslationOptions,
)
from indic_language_utils.translation.processing import Segment


@dataclass(frozen=True)
class PrefixProcessor:
    identity = ProcessorIdentity("test-prefix", "1")

    def prepare(self, segment: Segment, options: TranslationOptions) -> Segment:
        return Segment(
            f"X:{segment.text}",
            segment.prefix,
            segment.suffix,
            segment.protected,
            segment.state,
        ).with_state(self.identity.name, "X:")

    def restore(self, text: str, segment: Segment, options: TranslationOptions) -> str:
        prefix = segment.state_for(self.identity.name)
        if not isinstance(prefix, str) or not text.startswith(prefix):
            raise OutputValidationError("Custom prefix was not preserved")
        return text[len(prefix) :]


@dataclass
class FakeTranslationProvider:
    name: str = "fake"
    transform: Callable[[str], str] = lambda value: f"translated:{value}"
    malformed_batch_once: bool = False
    fail_with: BaseException | None = None
    service_id: str = "fake-service"
    calls: list[tuple[str, ...]] = field(default_factory=list)
    identity: ProviderIdentity = field(init=False)
    capabilities: tuple[CapabilityDeclaration, ...] = field(init=False)

    def __post_init__(self) -> None:
        self.identity = ProviderIdentity(self.name)
        languages = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (CapabilityDeclaration(CapabilityId.TRANSLATION, languages),)

    async def translate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TranslationOptions,
        request_id: str,
    ) -> ProviderTranslationResult:
        self.calls.append(texts)
        if self.fail_with:
            raise self.fail_with
        if self.malformed_batch_once and len(texts) > 1:
            self.malformed_batch_once = False
            return ProviderTranslationResult((self.transform(texts[0]),), self.service_id)
        return ProviderTranslationResult(
            tuple(self.transform(text) for text in texts), self.service_id, request_id=request_id
        )


def router_for(*providers: FakeTranslationProvider) -> OrderedRouter:
    registry = ProviderRegistry()
    for provider in providers:
        registry.register(provider)
    return OrderedRouter(
        registry,
        {CapabilityId.TRANSLATION: tuple(provider.name for provider in providers)},
    )
