"""Synchronous translation facade for scripts without an active event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from ..errors import InvalidInputError
from .client import TranslationClient
from .models import TranslationRequest, TranslationResult

T = TypeVar("T")


class SyncTranslationClient:
    def __init__(self, client: TranslationClient) -> None:
        self._client = client

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self._run(self._client.translate(request))

    def translate_batch(
        self, requests: tuple[TranslationRequest, ...]
    ) -> tuple[TranslationResult, ...]:
        return self._run(self._client.translate_batch(requests))

    @staticmethod
    def _run(coroutine: Coroutine[Any, Any, T]) -> T:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        coroutine.close()
        raise InvalidInputError(
            "The synchronous client cannot run inside an active event loop; use TranslationClient"
        )
