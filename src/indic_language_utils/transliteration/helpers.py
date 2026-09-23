"""User-friendly entry points and factory functions for transliteration."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..errors import ConfigurationError, MissingOptionalDependencyError
from ..languages import LanguageTag
from ..providers import CapabilityId, ProviderRegistry
from ..routing import OrderedRouter
from .cache import create_transliteration_cache
from .client import TransliterationClient
from .models import TransliterationOptions, TransliterationResult
from .protocols import TransliterationProvider
from .sync import SyncTransliterationClient


def get_transliteration_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TransliterationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> TransliterationClient:
    """Build and configure a TransliterationClient with providers, routes, and cache."""
    if settings is None:
        settings = Settings.load(env=env)

    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        env_map = os.environ if env is None else env

        # Check Bhashini transliteration adapter
        has_bhashini = (
            "bhashini" in settings.providers
            or "BHASHINI_API_KEY" in env_map
            or "BHASHINI_TRANSLITERATION_SERVICE_ID" in env_map
        )
        if has_bhashini:
            try:
                from ..providers.bhashini import BhashiniConfig
                from .bhashini_transliterate import BhashiniTransliterationProvider

                bhashini_config = BhashiniConfig.from_settings(settings, env=env)
                if (
                    bhashini_config.transliteration_service_id
                    or bhashini_config.transliteration_service_ids
                ):
                    registry.register(BhashiniTransliterationProvider(bhashini_config))
            except ConfigurationError:
                pass

        # Check IndicXlit local adapter
        try:
            from .indicxlit import (
                HAVE_INDICXLIT,
                IndicXlitConfig,
                IndicXlitTransliterationProvider,
            )

            if HAVE_INDICXLIT:
                registry.register(IndicXlitTransliterationProvider(IndicXlitConfig()))
        except (ConfigurationError, MissingOptionalDependencyError):
            pass

    registered_names = {p.identity.provider for p in registry.all()}
    routes: dict[CapabilityId, tuple[str, ...]] = {}
    if providers is not None:
        translit_providers = tuple(
            p.identity.provider
            for p in registry.all()
            if registry.declaration(p.identity.provider, CapabilityId.TRANSLITERATION) is not None
        )
        if translit_providers:
            routes[CapabilityId.TRANSLITERATION] = translit_providers
    else:
        for cap_str, provider_names in settings.routes.items():
            try:
                cap_id = CapabilityId(cap_str)
                valid_names = tuple(name for name in provider_names if name in registered_names)
                if valid_names:
                    routes[cap_id] = valid_names
            except ValueError:
                pass

        if CapabilityId.TRANSLITERATION not in routes or not routes[CapabilityId.TRANSLITERATION]:
            translit_providers = tuple(
                p.identity.provider
                for p in registry.all()
                if registry.declaration(p.identity.provider, CapabilityId.TRANSLITERATION)
                is not None
            )
            if translit_providers:
                routes[CapabilityId.TRANSLITERATION] = translit_providers

    router = OrderedRouter(registry, routes)
    cache = create_transliteration_cache(settings.cache)
    return TransliterationClient(router=router, cache=cache)


def get_sync_transliteration_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TransliterationProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> SyncTransliterationClient:
    """Build and configure a synchronous TransliterationClient facade."""
    return SyncTransliterationClient(
        get_transliteration_client(settings=settings, providers=providers, env=env)
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
