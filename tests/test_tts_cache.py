from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from indic_language_utils import Secret
from indic_language_utils.config import CacheSettings, Settings
from indic_language_utils.tts import TTSOptions, create_tts_cache, get_tts_client
from indic_language_utils.tts.bhashini import BhashiniTTSProvider

from .test_tts import FakeTransport, config, response


@pytest.mark.asyncio
async def test_tts_memory_cache_reuses_audio_and_separates_options() -> None:
    transport = FakeTransport([response(b"first-audio"), response(b"second-audio")])
    provider = BhashiniTTSProvider(config(), transport=transport)
    settings = Settings(cache=CacheSettings(enabled=True, backend="memory"))
    client = get_tts_client(settings, providers=[provider])

    first = await client.synthesize(
        "Hello", language="hi", options=TTSOptions({"gender": "female"})
    )
    cached = await client.synthesize(
        "Hello", language="hi", options=TTSOptions({"gender": "female"})
    )
    changed = await client.synthesize(
        "Hello", language="hi", options=TTSOptions({"gender": "male"})
    )

    assert first.audio == cached.audio == b"first-audio"
    assert changed.audio == b"second-audio"
    assert not first.cache.hit and cached.cache.hit and not changed.cache.hit
    assert cached.provider_request_id is None
    assert cached.request_id != first.request_id
    assert len(transport.payloads) == 2


@pytest.mark.asyncio
async def test_tts_model_change_invalidates_cache() -> None:
    settings = CacheSettings(enabled=True, backend="memory")
    cache = create_tts_cache(settings)
    first_provider = BhashiniTTSProvider(
        config(), transport=FakeTransport([response(b"model-one")])
    )
    changed_config = replace(config(), tts_model_id="new-model")
    second_provider = BhashiniTTSProvider(
        changed_config, transport=FakeTransport([response(b"model-two")])
    )
    first_client = get_tts_client(Settings(cache=settings), providers=[first_provider], cache=cache)
    second_client = get_tts_client(
        Settings(cache=settings), providers=[second_provider], cache=cache
    )

    first = await first_client.synthesize("Hello")
    second = await second_client.synthesize("Hello")

    assert first.audio == b"model-one"
    assert second.audio == b"model-two"
    assert not second.cache.hit


@pytest.mark.asyncio
async def test_tts_sqlite_cache_survives_client_restart(tmp_path: Path) -> None:
    settings = Settings(
        cache=CacheSettings(
            enabled=True,
            backend="sqlite",
            path=str(tmp_path / "tts.sqlite3"),
        )
    )
    first_provider = BhashiniTTSProvider(
        config(), transport=FakeTransport([response(b"persistent-audio")])
    )
    first_client = get_tts_client(settings, providers=[first_provider])
    await first_client.synthesize("Hello")

    restarted_transport = FakeTransport([])
    restarted_provider = BhashiniTTSProvider(config(), transport=restarted_transport)
    restarted_client = get_tts_client(settings, providers=[restarted_provider])
    cached = await restarted_client.synthesize("Hello")

    assert cached.audio == b"persistent-audio"
    assert cached.cache.hit
    assert not restarted_transport.payloads


@pytest.mark.asyncio
async def test_tts_audio_over_byte_budget_is_not_cached() -> None:
    settings = Settings(cache=CacheSettings(enabled=True, backend="memory", tts_max_bytes=4))
    transport = FakeTransport([response(b"large-audio"), response(b"large-audio")])
    client = get_tts_client(
        settings, providers=[BhashiniTTSProvider(config(), transport=transport)]
    )

    await client.synthesize("Hello")
    repeated = await client.synthesize("Hello")

    assert not repeated.cache.hit
    assert len(transport.payloads) == 2


@pytest.mark.asyncio
async def test_tts_cache_separates_provider_credentials() -> None:
    settings = CacheSettings(enabled=True, backend="memory")
    cache = create_tts_cache(settings)
    first_transport = FakeTransport([response(b"first-account")])
    second_transport = FakeTransport([response(b"second-account")])
    first_provider = BhashiniTTSProvider(config(), transport=first_transport)
    second_provider = BhashiniTTSProvider(
        replace(config(), api_key=Secret("different-key")), transport=second_transport
    )
    first_client = get_tts_client(Settings(cache=settings), providers=[first_provider], cache=cache)
    second_client = get_tts_client(
        Settings(cache=settings), providers=[second_provider], cache=cache
    )

    first = await first_client.synthesize("Hello")
    second = await second_client.synthesize("Hello")

    assert first.audio == b"first-account"
    assert second.audio == b"second-account"
    assert not second.cache.hit
