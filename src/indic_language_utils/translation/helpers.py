"""User-friendly entry points and factory functions for translation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..errors import InvalidInputError
from ..languages import LanguageRegistry, LanguageTag
from ..providers import CapabilityId, ProviderRegistry
from ..providers.factories import ProviderFactoryRegistry, configured_provider_factories
from ..routing import OrderedRouter
from .cache import create_translation_cache
from .client import TranslationClient
from .models import TranslationOptions, TranslationResult
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
    for cap_str, provider_names in settings.routes.items() if use_configured_routes else ():
        try:
            cap_id = CapabilityId(cap_str)
            valid_names = tuple(name for name in provider_names if name in registered_names)
            if valid_names:
                routes[cap_id] = valid_names
        except ValueError:
            pass

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

    router = OrderedRouter(registry, routes)
    cache = create_translation_cache(settings.cache, language_registry=language_registry)
    return TranslationClient(router=router, cache=cache, language_registry=language_registry)


def get_sync_translation_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TranslationProvider] | None = None,
    additional_providers: Sequence[TranslationProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
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
