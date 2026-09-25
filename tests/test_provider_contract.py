from __future__ import annotations

import asyncio

import pytest

from indic_language_utils import Settings, get_translation_client
from indic_language_utils.errors import TransientProviderError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
from indic_language_utils.testing import (
    assert_batch_output,
    assert_cancellation,
    assert_declared_support,
    assert_fallback_result,
    assert_valid_declaration,
)

from .support import FakeProvider
from .translation_support import FakeTranslationProvider


def test_contract_checks_declaration_and_batch_shape() -> None:
    provider = FakeProvider("sample", (CapabilityDeclaration(CapabilityId.TRANSLATION),))
    assert_valid_declaration(provider, CapabilityId.TRANSLATION)
    assert_declared_support(
        provider,
        CapabilityId.TRANSLATION,
        source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        expected=True,
    )
    assert_batch_output(("one", "two"), 2, valid_item=lambda text: bool(text))
    with pytest.raises(AssertionError, match="wrong number"):
        assert_batch_output(("one",), 2, valid_item=lambda text: bool(text))


@pytest.mark.asyncio
async def test_contract_detects_swallowed_cancellation() -> None:
    started = asyncio.Event()

    async def swallowing_operation() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return

    with pytest.raises(AssertionError, match="swallowed cancellation"):
        await assert_cancellation(swallowing_operation, started=started)


@pytest.mark.asyncio
async def test_contract_checks_fallback_through_public_client() -> None:
    failing = FakeTranslationProvider("failing", fail_with=TransientProviderError("temporary"))
    working = FakeTranslationProvider("working")
    async with get_translation_client(Settings(), providers=[failing, working], env={}) as client:
        result = await client.translate("hello", "en", "hi")
    assert_fallback_result(result, provider_id="working")
