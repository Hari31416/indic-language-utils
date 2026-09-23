"""Synchronous transliteration facade for scripts without an active event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any, TypeVar, cast, overload

from ..errors import InvalidInputError
from ..languages import LanguageTag
from ..models import OperationContext
from .client import TransliterationClient
from .models import (
    TransliterationOptions,
    TransliterationRequest,
    TransliterationResult,
)

T = TypeVar("T")


class SyncTransliterationClient:
    def __init__(self, client: TransliterationClient) -> None:
        self._client = client

    @overload
    def transliterate(self, request: TransliterationRequest, /) -> TransliterationResult: ...

    @overload
    def transliterate(
        self,
        text: str,
        /,
        *,
        source: LanguageTag | str,
        target: LanguageTag | str,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> TransliterationResult: ...

    def transliterate(
        self,
        request_or_text: TransliterationRequest | str,
        *,
        source: LanguageTag | str | None = None,
        target: LanguageTag | str | None = None,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> TransliterationResult:
        if isinstance(request_or_text, TransliterationRequest):
            return self._run(self._client.transliterate(request_or_text))
        if source is None or target is None:
            raise ValueError("source and target are required when providing text as string")
        return self._run(
            self._client.transliterate(
                request_or_text,
                source=source,
                target=target,
                options=options,
                context=context,
            )
        )

    @overload
    def transliterate_batch(
        self,
        requests: Sequence[TransliterationRequest],
        /,
    ) -> tuple[TransliterationResult, ...]: ...

    @overload
    def transliterate_batch(
        self,
        texts: Sequence[str],
        /,
        *,
        source: LanguageTag | str,
        target: LanguageTag | str,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TransliterationResult, ...]: ...

    def transliterate_batch(
        self,
        requests_or_texts: Sequence[TransliterationRequest] | Sequence[str],
        *,
        source: LanguageTag | str | None = None,
        target: LanguageTag | str | None = None,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TransliterationResult, ...]:
        if not requests_or_texts:
            return ()
        first = requests_or_texts[0]
        if isinstance(first, TransliterationRequest):
            return self._run(
                self._client.transliterate_batch(
                    cast(Sequence[TransliterationRequest], requests_or_texts)
                )
            )
        if source is None or target is None:
            raise ValueError("source and target are required when providing texts as strings")
        return self._run(
            self._client.transliterate_batch(
                cast(Sequence[str], requests_or_texts),
                source=source,
                target=target,
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
            "The synchronous client cannot run inside an active event loop; "
            "use TransliterationClient"
        )
