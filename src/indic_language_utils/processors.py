"""Shared identity contract for capability-specific processors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True, order=True)
class ProcessorIdentity:
    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("Processor name and version cannot be empty")


@runtime_checkable
class VersionedProcessor(Protocol):
    identity: ProcessorIdentity
