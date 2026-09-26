"""User-friendly entry points and factory functions for translation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from ..cache import AsyncCache, CacheKeyBuilder
from ..config import Settings
from ..errors import InvalidInputError
from ..languages import LanguageRegistry, LanguageTag
from ..providers import CapabilityId, ProviderRegistry
from ..providers.factories import (
    ProviderFactoryRegistry,
    configured_provider_factories,
    default_provider_factories,
)
from ..routing import OrderedRouter, RouteSelector, resolve_route_names
from ..telemetry import EventLogger, MetricHook, TraceHook
from .cache import SegmentTranslation, create_translation_cache, create_translation_segment_cache
from .catalog import LocalizationCatalog
from .client import TranslationClient
from .models import TranslationOptions, TranslationResult
from .processing import TranslationProcessorPipeline
from .protocols import TranslationProvider
from .sync import SyncTranslationClient


def get_translation_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TranslationProvider] | None = None,
    additional_providers: Sequence[TranslationProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
    cache: AsyncCache[TranslationResult] | None = None,
    segment_cache: AsyncCache[SegmentTranslation] | None = None,
    cache_keys: CacheKeyBuilder | None = None,
    catalog: LocalizationCatalog | None = None,
    logger: EventLogger | None = None,
    metrics: MetricHook | None = None,
    tracing: TraceHook | None = None,
    processors: TranslationProcessorPipeline | None = None,
    route_selector: RouteSelector | None = None,
) -> TranslationClient:
    """Build and configure a TranslationClient with providers, routes, and cache.

    If settings are not provided, they are loaded from discovered configuration files
    and the environment. If providers are not provided, built-in providers (such as
    Bhashini) are registered if configured or if their credentials exist in the environment.
    """
    use_configured_routes = providers is None or settings is not None
    if settings is None:
        settings = Settings.load(env=env)

    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        values = os.environ if env is None else env
        for built_provider in configured_provider_factories(
            CapabilityId.TRANSLATION, settings, provider_factories
        ).build(CapabilityId.TRANSLATION, settings, values):
            registry.register(built_provider)

    for provider in additional_providers:
        registry.register(provider)

    registered_names = {p.identity.provider for p in registry.all()}
    routes: dict[CapabilityId, tuple[str, ...]] = {}
    configured = (
        settings.routes.get(CapabilityId.TRANSLATION.value) if use_configured_routes else None
    )
    if configured is not None:
        known = set(registered_names)
        if providers is None:
            factories = provider_factories or default_provider_factories()
            known.update(
                item.provider_id for item in factories.for_capability(CapabilityId.TRANSLATION)
            )
        routes[CapabilityId.TRANSLATION] = resolve_route_names(
            CapabilityId.TRANSLATION, configured, registered_names, known
        )

    if providers is None:
        env_map = os.environ if env is None else env
        active_service = env_map.get("TRANSLATION_SERVICE_PROVIDER")
        if active_service in registered_names and CapabilityId.TRANSLATION in routes:
            current_route = routes[CapabilityId.TRANSLATION]
            routes[CapabilityId.TRANSLATION] = (
                active_service,
                *(p for p in current_route if p != active_service),
            )

    if CapabilityId.TRANSLATION not in routes or not routes[CapabilityId.TRANSLATION]:
        trans_providers = tuple(
            p.identity.provider
            for p in registry.all()
            if registry.declaration(p.identity.provider, CapabilityId.TRANSLATION) is not None
        )
        if providers is None and active_service in registered_names and trans_providers:
            trans_providers = (
                active_service,
                *(p for p in trans_providers if p != active_service),
            )
        if trans_providers:
            routes[CapabilityId.TRANSLATION] = trans_providers

    router = OrderedRouter(registry, routes, selector=route_selector)
    selected_cache = (
        cache
        if cache is not None
        else create_translation_cache(settings.cache, language_registry=language_registry)
    )
    selected_segment_cache = segment_cache
    if (
        selected_segment_cache is None
        and cache is None
        and settings.cache.enabled
        and settings.cache.backend != "null"
    ):
        selected_segment_cache = create_translation_segment_cache(settings.cache)
    return TranslationClient(
        router=router,
        cache=selected_cache,
        segment_cache=selected_segment_cache,
        cache_keys=cache_keys,
        catalog=catalog,
        logger=logger,
        metrics=metrics,
        tracing=tracing,
        processors=processors,
        language_registry=language_registry,
    )


def get_sync_translation_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TranslationProvider] | None = None,
    additional_providers: Sequence[TranslationProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
    cache: AsyncCache[TranslationResult] | None = None,
    segment_cache: AsyncCache[SegmentTranslation] | None = None,
    cache_keys: CacheKeyBuilder | None = None,
    catalog: LocalizationCatalog | None = None,
    logger: EventLogger | None = None,
    metrics: MetricHook | None = None,
    tracing: TraceHook | None = None,
    processors: TranslationProcessorPipeline | None = None,
    route_selector: RouteSelector | None = None,
) -> SyncTranslationClient:
    """Build and configure a synchronous TranslationClient facade."""
    return SyncTranslationClient(
        get_translation_client(
            settings=settings,
            providers=providers,
            additional_providers=additional_providers,
            provider_factories=provider_factories,
            env=env,
            language_registry=language_registry,
            cache=cache,
            segment_cache=segment_cache,
            cache_keys=cache_keys,
            catalog=catalog,
            logger=logger,
            metrics=metrics,
            tracing=tracing,
            processors=processors,
            route_selector=route_selector,
        )
    )


async def translate(
    text: str,
    source: str | LanguageTag,
    target: str | LanguageTag,
    *,
    options: TranslationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TranslationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> TranslationResult:
    """Translate a single text using a managed async TranslationClient lifecycle."""
    async with get_translation_client(settings=settings, providers=providers, env=env) as client:
        return await client.translate(text, source, target, options=options)


def translate_sync(
    text: str,
    source: str | LanguageTag,
    target: str | LanguageTag,
    *,
    options: TranslationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TranslationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> TranslationResult:
    """Translate a single text synchronously using a managed client lifecycle."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            translate(
                text,
                source,
                target,
                options=options,
                settings=settings,
                providers=providers,
                env=env,
            )
        )
    raise InvalidInputError(
        "translate_sync cannot run inside an active event loop; use await translate(...)"
    )


async def translate_batch(
    texts: Sequence[str],
    source: str | LanguageTag,
    target: str | LanguageTag,
    *,
    options: TranslationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TranslationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[TranslationResult, ...]:
    """Translate multiple texts using a managed async TranslationClient lifecycle."""
    async with get_translation_client(settings=settings, providers=providers, env=env) as client:
        return await client.translate_batch(texts, source, target, options=options)


def translate_batch_sync(
    texts: Sequence[str],
    source: str | LanguageTag,
    target: str | LanguageTag,
    *,
    options: TranslationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TranslationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[TranslationResult, ...]:
    """Translate multiple texts synchronously using a managed client lifecycle."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            translate_batch(
                texts,
                source,
                target,
                options=options,
                settings=settings,
                providers=providers,
                env=env,
            )
        )
    raise InvalidInputError(
        "translate_batch_sync cannot run inside an active event loop; "
        "use await translate_batch(...)"
    )
