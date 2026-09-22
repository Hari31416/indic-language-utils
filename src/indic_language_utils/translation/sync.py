"""Synchronous translation facade for scripts without an active event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any, TypeVar, cast, overload

from ..errors import InvalidInputError
from ..languages import LanguageTag
from ..models import OperationContext
from .client import TranslationClient
from .models import TranslationOptions, TranslationRequest, TranslationResult

T = TypeVar("T")


class SyncTranslationClient:
    def __init__(self, client: TranslationClient) -> None:
        self._client = client

    @overload
    def translate(self, request: TranslationRequest, /) -> TranslationResult: ...

    @overload
    def translate(
        self,
        text: str,
        source: str | LanguageTag,
        target: str | LanguageTag,
        /,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
        message_id: str | None = None,
    ) -> TranslationResult: ...

    def translate(
        self,
        request_or_text: TranslationRequest | str,
        source: str | LanguageTag | None = None,
        target: str | LanguageTag | None = None,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
        message_id: str | None = None,
    ) -> TranslationResult:
        if isinstance(request_or_text, TranslationRequest):
            return self._run(self._client.translate(request_or_text))
        if source is None or target is None:
            raise ValueError("Source and target languages are required when translating text")
        return self._run(
            self._client.translate(
                request_or_text,
                source,
                target,
                options=options,
                context=context,
                message_id=message_id,
            )
        )

    @overload
    def translate_batch(
        self,
        requests: Sequence[TranslationRequest],
        /,
    ) -> tuple[TranslationResult, ...]: ...

    @overload
    def translate_batch(
        self,
        texts: Sequence[str],
        source: str | LanguageTag,
        target: str | LanguageTag,
        /,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TranslationResult, ...]: ...

    def translate_batch(
        self,
        requests_or_texts: Sequence[TranslationRequest] | Sequence[str],
        source: str | LanguageTag | None = None,
        target: str | LanguageTag | None = None,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TranslationResult, ...]:
        if not requests_or_texts:
            return ()
        first = requests_or_texts[0]
        if isinstance(first, TranslationRequest):
            return self._run(
                self._client.translate_batch(cast(Sequence[TranslationRequest], requests_or_texts))
            )
        if source is None or target is None:
            raise ValueError("Source and target languages are required when translating texts")
        return self._run(
            self._client.translate_batch(
                cast(Sequence[str], requests_or_texts),
                source,
                target,
                options=options,
                context=context,
            )
        )

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
