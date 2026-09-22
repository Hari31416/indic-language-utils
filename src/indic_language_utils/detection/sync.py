"""Synchronous language detection facade for scripts without an active event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any, TypeVar, cast, overload

from ..errors import InvalidInputError
from ..models import OperationContext
from .client import DetectionClient
from .models import DetectionOptions, DetectionRequest, DetectionResult

T = TypeVar("T")


class SyncDetectionClient:
    def __init__(self, client: DetectionClient) -> None:
        self._client = client

    @overload
    def detect(self, request: DetectionRequest, /) -> DetectionResult: ...

    @overload
    def detect(
        self,
        text: str,
        /,
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> DetectionResult: ...

    def detect(
        self,
        request_or_text: DetectionRequest | str,
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> DetectionResult:
        if isinstance(request_or_text, DetectionRequest):
            return self._run(self._client.detect(request_or_text))
        return self._run(self._client.detect(request_or_text, options=options, context=context))

    @overload
    def detect_batch(
        self,
        requests: Sequence[DetectionRequest],
        /,
    ) -> tuple[DetectionResult, ...]: ...

    @overload
    def detect_batch(
        self,
        texts: Sequence[str],
        /,
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[DetectionResult, ...]: ...

    def detect_batch(
        self,
        requests_or_texts: Sequence[DetectionRequest] | Sequence[str],
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[DetectionResult, ...]:
        if not requests_or_texts:
            return ()
        first = requests_or_texts[0]
        if isinstance(first, DetectionRequest):
            return self._run(
                self._client.detect_batch(cast(Sequence[DetectionRequest], requests_or_texts))
            )
        return self._run(
            self._client.detect_batch(
                cast(Sequence[str], requests_or_texts),
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
            "The synchronous client cannot run inside an active event loop; use DetectionClient"
        )
