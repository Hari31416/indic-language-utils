"""User-friendly entry points and factory functions for transliteration."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from ..cache import AsyncCache, CacheKeyBuilder
from ..config import Settings
from ..languages import LanguageRegistry, LanguageTag
from ..providers import CapabilityId, ProviderRegistry
from ..providers.factories import (
    ProviderFactoryRegistry,
    configured_provider_factories,
    default_provider_factories,
)
from ..routing import OrderedRouter, RouteSelector, resolve_route_names
from ..telemetry import EventLogger, MetricHook, TraceHook
from .cache import create_transliteration_cache
from .client import TransliterationClient
from .models import TransliterationOptions, TransliterationResult
from .protocols import TransliterationProvider
from .sync import SyncTransliterationClient


def get_transliteration_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TransliterationProvider] | None = None,
    additional_providers: Sequence[TransliterationProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
    cache: AsyncCache[TransliterationResult] | None = None,
    cache_keys: CacheKeyBuilder | None = None,
    logger: EventLogger | None = None,
    metrics: MetricHook | None = None,
    tracing: TraceHook | None = None,
    route_selector: RouteSelector | None = None,
) -> TransliterationClient:
    """Build and configure a TransliterationClient with providers, routes, and cache."""
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
            CapabilityId.TRANSLITERATION, settings, provider_factories
        ).build(CapabilityId.TRANSLITERATION, settings, values):
            registry.register(built_provider)

    for provider in additional_providers:
        registry.register(provider)

    registered_names = {p.identity.provider for p in registry.all()}
    routes: dict[CapabilityId, tuple[str, ...]] = {}
    configured = (
        settings.routes.get(CapabilityId.TRANSLITERATION.value) if use_configured_routes else None
    )
    if configured is not None:
        known = set(registered_names)
        if providers is None:
            factories = provider_factories or default_provider_factories()
            known.update(
                item.provider_id for item in factories.for_capability(CapabilityId.TRANSLITERATION)
            )
        routes[CapabilityId.TRANSLITERATION] = resolve_route_names(
            CapabilityId.TRANSLITERATION, configured, registered_names, known
        )

    if CapabilityId.TRANSLITERATION not in routes:
        priority = ("bhashini", "aksharamukha", "indicxlit")
        ordered = [name for name in priority if name in registered_names]
        for registered_provider in registry.all():
            name = registered_provider.identity.provider
            if (
                name not in ordered
                and registry.declaration(name, CapabilityId.TRANSLITERATION) is not None
            ):
                ordered.append(name)
        if ordered:
            routes[CapabilityId.TRANSLITERATION] = tuple(ordered)

    router = OrderedRouter(registry, routes, selector=route_selector)
    selected_cache = cache if cache is not None else create_transliteration_cache(settings.cache)
    return TransliterationClient(
        router=router,
        cache=selected_cache,
        cache_keys=cache_keys,
        logger=logger,
        metrics=metrics,
        tracing=tracing,
        language_registry=language_registry,
    )


def get_sync_transliteration_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TransliterationProvider] | None = None,
    additional_providers: Sequence[TransliterationProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
    cache: AsyncCache[TransliterationResult] | None = None,
    cache_keys: CacheKeyBuilder | None = None,
    logger: EventLogger | None = None,
    metrics: MetricHook | None = None,
    tracing: TraceHook | None = None,
    route_selector: RouteSelector | None = None,
) -> SyncTransliterationClient:
    """Build and configure a synchronous TransliterationClient facade."""
    return SyncTransliterationClient(
        get_transliteration_client(
            settings=settings,
            providers=providers,
            additional_providers=additional_providers,
            provider_factories=provider_factories,
            env=env,
            language_registry=language_registry,
            cache=cache,
            cache_keys=cache_keys,
            logger=logger,
            metrics=metrics,
            tracing=tracing,
            route_selector=route_selector,
        )
    )


async def transliterate(
    text: str,
    *,
    source: LanguageTag | str,
    target: LanguageTag | str,
    options: TransliterationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TransliterationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> TransliterationResult:
    """Transliterate text using a managed async TransliterationClient lifecycle."""
    async with get_transliteration_client(
        settings=settings, providers=providers, env=env
    ) as client:
        return await client.transliterate(text, source=source, target=target, options=options)


def transliterate_sync(
    text: str,
    *,
    source: LanguageTag | str,
    target: LanguageTag | str,
    options: TransliterationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TransliterationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> TransliterationResult:
    """Transliterate text synchronously using a managed client lifecycle."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            transliterate(
                text,
                source=source,
                target=target,
                options=options,
                settings=settings,
                providers=providers,
                env=env,
            )
        )
    return get_sync_transliteration_client(
        settings=settings, providers=providers, env=env
    ).transliterate(text, source=source, target=target, options=options)


async def transliterate_batch(
    texts: Sequence[str],
    *,
    source: LanguageTag | str,
    target: LanguageTag | str,
    options: TransliterationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TransliterationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[TransliterationResult, ...]:
    """Transliterate multiple texts using a managed async TransliterationClient lifecycle."""
    async with get_transliteration_client(
        settings=settings, providers=providers, env=env
    ) as client:
        return await client.transliterate_batch(
            texts, source=source, target=target, options=options
        )


def transliterate_batch_sync(
    texts: Sequence[str],
    *,
    source: LanguageTag | str,
    target: LanguageTag | str,
    options: TransliterationOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[TransliterationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[TransliterationResult, ...]:
    """Transliterate multiple texts synchronously using a managed client lifecycle."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            transliterate_batch(
                texts,
                source=source,
                target=target,
                options=options,
                settings=settings,
                providers=providers,
                env=env,
            )
        )
    return get_sync_transliteration_client(
        settings=settings, providers=providers, env=env
    ).transliterate_batch(texts, source=source, target=target, options=options)
