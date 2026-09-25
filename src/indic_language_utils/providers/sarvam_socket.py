"""Small WebSocket transport shared by Sarvam speech streams."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from ..errors import MissingOptionalDependencyError
from .sarvam import SarvamConfig


class Socket(Protocol):
    async def send(self, message: str) -> None: ...

    def __aiter__(self) -> AsyncIterator[str | bytes]: ...


@asynccontextmanager
async def connect(config: SarvamConfig, path: str) -> AsyncIterator[Socket]:
    try:
        from websockets.asyncio.client import connect as ws_connect
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "Install indic-language-utils[streaming] for Sarvam speech streams",
            provider="sarvam",
        ) from exc

    endpoint = config.endpoint.rstrip("/")
    url = endpoint.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + path
    async with ws_connect(
        url,
        additional_headers={"api-subscription-key": config.api_key.reveal()},
        open_timeout=config.timeout_seconds,
    ) as socket:
        yield socket
