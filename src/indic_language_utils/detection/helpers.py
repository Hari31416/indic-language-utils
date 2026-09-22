"""User-friendly entry points and factory functions for text language detection."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..errors import ConfigurationError, MissingOptionalDependencyError
from ..providers import CapabilityId, ProviderRegistry
from ..routing import OrderedRouter
from .cache import create_detection_cache
from .client import DetectionClient
from .models import DetectionOptions, DetectionResult
from .protocols import DetectionProvider
from .sync import SyncDetectionClient


def get_detection_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[DetectionProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> DetectionClient:
    """Build and configure a DetectionClient with providers, routes, and cache."""
    if settings is None:
        settings = Settings.load(env=env)

    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        env_map = os.environ if env is None else env

        # Check Bhashini detection adapter
        has_bhashini = (
            "bhashini" in settings.providers
            or "BHASHINI_API_KEY" in env_map
            or "BHASHINI_DETECTION_SERVICE_ID" in env_map
            or "BHASHINI_TLD_SERVICE_ID" in env_map
        )
        if has_bhashini:
            try:
                from ..bhashini import BhashiniConfig, BhashiniDetectionProvider

                bhashini_config = BhashiniConfig.from_settings(settings, env=env)
                if bhashini_config.detection_service_id:
                    registry.register(BhashiniDetectionProvider(bhashini_config))
            except ConfigurationError:
                pass

        # Default local detection adapter: FastText
        try:
            from .fasttext import HAVE_FASTTEXT, FastTextDetectionConfig, FastTextDetectionProvider

            if HAVE_FASTTEXT:
                registry.register(FastTextDetectionProvider(FastTextDetectionConfig()))
        except (ConfigurationError, MissingOptionalDependencyError):
            pass

    registered_names = {p.identity.provider for p in registry.all()}
    routes: dict[CapabilityId, tuple[str, ...]] = {}
    if providers is not None:
        detect_providers = tuple(
            p.identity.provider
            for p in registry.all()
            if registry.declaration(p.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION)
            is not None
        )
        if detect_providers:
            routes[CapabilityId.TEXT_LANGUAGE_DETECTION] = detect_providers
    else:
        for cap_str, provider_names in settings.routes.items():
            try:
                cap_id = CapabilityId(cap_str)
                valid_names = tuple(name for name in provider_names if name in registered_names)
                if valid_names:
                    routes[cap_id] = valid_names
            except ValueError:
                pass

        if (
            CapabilityId.TEXT_LANGUAGE_DETECTION not in routes
            or not routes[CapabilityId.TEXT_LANGUAGE_DETECTION]
        ):
            detect_providers = tuple(
                p.identity.provider
                for p in registry.all()
                if registry.declaration(p.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION)
                is not None
            )
            if detect_providers:
                routes[CapabilityId.TEXT_LANGUAGE_DETECTION] = detect_providers

    router = OrderedRouter(registry, routes)
    cache = create_detection_cache(settings.cache)
    return DetectionClient(router=router, cache=cache)


def get_sync_detection_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[DetectionProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> SyncDetectionClient:
    """Build and configure a synchronous DetectionClient facade."""
    return SyncDetectionClient(
        get_detection_client(settings=settings, providers=providers, env=env)
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
