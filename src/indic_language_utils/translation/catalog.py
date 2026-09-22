"""Reviewed exact-match translations kept separate from runtime caching."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ..errors import ConfigurationError
from ..languages import LanguageTag


class CatalogStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    message_id: str
    source_text: str
    translated_text: str
    source: LanguageTag
    target: LanguageTag
    version: str
    provenance: str
    status: CatalogStatus
    reviewer: str | None = None


class LocalizationCatalog:
    def __init__(self, entries: Iterable[CatalogEntry] = (), *, version: str = "none") -> None:
        if not version:
            raise ConfigurationError("Catalog version cannot be empty")
        self.version = version
        self._entries: dict[tuple[str, LanguageTag, LanguageTag], CatalogEntry] = {}
        for entry in entries:
            key = (entry.message_id, entry.source, entry.target)
            if key in self._entries:
                raise ConfigurationError("Catalog contains a duplicate message and language pair")
            self._entries[key] = entry

    def lookup(
        self,
        message_id: str | None,
        source_text: str,
        source: LanguageTag,
        target: LanguageTag,
    ) -> CatalogEntry | None:
        if message_id is None:
            return None
        entry = self._entries.get((message_id, source, target))
        if (
            entry is None
            or entry.status is not CatalogStatus.REVIEWED
            or entry.source_text != source_text
        ):
            return None
        return entry
