"""User-friendly entry points and factory functions for text language detection."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from ..cache import AsyncCache, CacheKeyBuilder
from ..config import Settings
from ..providers import CapabilityId, ProviderRegistry
from ..providers.factories import (
    ProviderFactoryRegistry,
    configured_provider_factories,
    default_provider_factories,
)
from ..routing import OrderedRouter, RouteSelector, resolve_route_names
from ..telemetry import EventLogger, MetricHook, TraceHook
from .cache import create_detection_cache
from .client import DetectionClient
from .models import DetectionOptions, DetectionResult
from .protocols import DetectionProvider
from .sync import SyncDetectionClient


def get_detection_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[DetectionProvider] | None = None,
    additional_providers: Sequence[DetectionProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    cache: AsyncCache[DetectionResult] | None = None,
    cache_keys: CacheKeyBuilder | None = None,
    logger: EventLogger | None = None,
    metrics: MetricHook | None = None,
    tracing: TraceHook | None = None,
    route_selector: RouteSelector | None = None,
) -> DetectionClient:
    """Build and configure a DetectionClient with providers, routes, and cache."""
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
            CapabilityId.TEXT_LANGUAGE_DETECTION, settings, provider_factories
        ).build(CapabilityId.TEXT_LANGUAGE_DETECTION, settings, values):
            registry.register(built_provider)

    for provider in additional_providers:
        registry.register(provider)

    registered_names = {p.identity.provider for p in registry.all()}
    routes: dict[CapabilityId, tuple[str, ...]] = {}
    configured = (
        settings.routes.get(CapabilityId.TEXT_LANGUAGE_DETECTION.value)
        if use_configured_routes
        else None
    )
    if configured is not None:
        known = set(registered_names)
        if providers is None:
            factories = provider_factories or default_provider_factories()
            known.update(
                item.provider_id
                for item in factories.for_capability(CapabilityId.TEXT_LANGUAGE_DETECTION)
            )
        routes[CapabilityId.TEXT_LANGUAGE_DETECTION] = resolve_route_names(
            CapabilityId.TEXT_LANGUAGE_DETECTION, configured, registered_names, known
        )

    if CapabilityId.TEXT_LANGUAGE_DETECTION not in routes:
        detect_providers = tuple(
            p.identity.provider
            for p in registry.all()
            if registry.declaration(p.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION)
            is not None
        )
        if detect_providers:
            routes[CapabilityId.TEXT_LANGUAGE_DETECTION] = detect_providers

    router = OrderedRouter(registry, routes, selector=route_selector)
    selected_cache = cache if cache is not None else create_detection_cache(settings.cache)
    return DetectionClient(
        router=router,
        cache=selected_cache,
        cache_keys=cache_keys,
        logger=logger,
        metrics=metrics,
        tracing=tracing,
    )


def get_sync_detection_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[DetectionProvider] | None = None,
    additional_providers: Sequence[DetectionProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    cache: AsyncCache[DetectionResult] | None = None,
    cache_keys: CacheKeyBuilder | None = None,
    logger: EventLogger | None = None,
    metrics: MetricHook | None = None,
    tracing: TraceHook | None = None,
    route_selector: RouteSelector | None = None,
) -> SyncDetectionClient:
    """Build and configure a synchronous DetectionClient facade."""
    return SyncDetectionClient(
        get_detection_client(
            settings=settings,
            providers=providers,
            additional_providers=additional_providers,
            provider_factories=provider_factories,
            env=env,
            cache=cache,
            cache_keys=cache_keys,
            logger=logger,
            metrics=metrics,
            tracing=tracing,
            route_selector=route_selector,
        )
    )


async def detect(
    text: str,
    *,
    options: DetectionOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[DetectionProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> DetectionResult:
    """Detect language of a single text using a managed async DetectionClient lifecycle."""
    async with get_detection_client(settings=settings, providers=providers, env=env) as client:
        return await client.detect(text, options=options)


def detect_sync(
    text: str,
    *,
    options: DetectionOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[DetectionProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> DetectionResult:
    """Detect language of a single text synchronously using a managed client lifecycle."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            detect(text, options=options, settings=settings, providers=providers, env=env)
        )
    return get_sync_detection_client(settings=settings, providers=providers, env=env).detect(
        text, options=options
    )


async def detect_batch(
    texts: Sequence[str],
    *,
    options: DetectionOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[DetectionProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[DetectionResult, ...]:
    """Detect languages for multiple texts using a managed async DetectionClient lifecycle."""
    async with get_detection_client(settings=settings, providers=providers, env=env) as client:
        return await client.detect_batch(texts, options=options)


def detect_batch_sync(
    texts: Sequence[str],
    *,
    options: DetectionOptions | None = None,
    settings: Settings | None = None,
    providers: Sequence[DetectionProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[DetectionResult, ...]:
    """Detect languages for multiple texts synchronously using a managed client lifecycle."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            detect_batch(texts, options=options, settings=settings, providers=providers, env=env)
        )
    return get_sync_detection_client(settings=settings, providers=providers, env=env).detect_batch(
        texts, options=options
    )
