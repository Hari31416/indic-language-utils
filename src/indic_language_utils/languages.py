"""Canonical public language tags and the library language registry."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import UnsupportedLanguageError

_TAG_PATTERN = re.compile(
    r"^(?P<language>[A-Za-z]{2,3})(?:[-_](?P<script>[A-Za-z]{4}))?(?:[-_](?P<region>[A-Za-z]{2}|[0-9]{3}))?$"
)


@dataclass(frozen=True, slots=True, order=True)
class LanguageTag:
    language: str
    script: str | None = None
    region: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z]{2,3}", self.language):
            raise ValueError("language must be a two- or three-letter lowercase code")
        if self.script is not None and not re.fullmatch(r"[A-Z][a-z]{3}", self.script):
            raise ValueError("script must use BCP 47 title case")
        if self.region is not None and not re.fullmatch(r"(?:[A-Z]{2}|[0-9]{3})", self.region):
            raise ValueError("region must be an uppercase country code or three digits")

    @classmethod
    def parse(cls, value: str) -> LanguageTag:
        match = _TAG_PATTERN.fullmatch(value.strip())
        if match is None:
            raise UnsupportedLanguageError("Unknown or malformed language tag")
        language = match.group("language").lower()
        script_raw = match.group("script")
        region_raw = match.group("region")
        script = script_raw.title() if script_raw else None
        region = region_raw.upper() if region_raw and region_raw.isalpha() else region_raw
        return cls(language, script, region)

    def __str__(self) -> str:
        return "-".join(part for part in (self.language, self.script, self.region) if part)

    def to_dict(self) -> dict[str, str | None]:
        return {
            "tag": str(self),
            "language": self.language,
            "script": self.script,
            "region": self.region,
        }


@dataclass(frozen=True, slots=True)
class LanguageDefinition:
    tag: LanguageTag
    name: str
    aliases: frozenset[str] = frozenset()


class LanguageRegistry:
    def __init__(self, definitions: Iterable[LanguageDefinition]) -> None:
        self._definitions: dict[str, LanguageDefinition] = {}
        self._aliases: dict[str, str] = {}
        for definition in definitions:
            canonical = str(definition.tag)
            if canonical in self._definitions:
                raise ValueError(f"Duplicate language tag: {canonical}")
            self._definitions[canonical] = definition
            for alias in {canonical, definition.tag.language, *definition.aliases}:
                key = alias.strip().lower().replace("_", "-")
                previous = self._aliases.get(key)
                if previous is not None and previous != canonical:
                    raise ValueError(f"Ambiguous language alias: {alias}")
                self._aliases[key] = canonical

    def normalize(self, value: str | LanguageTag) -> LanguageTag:
        if isinstance(value, LanguageTag):
            parsed = value
        else:
            key = value.strip().lower().replace("_", "-")
            canonical = self._aliases.get(key)
            if canonical is not None:
                return self._definitions[canonical].tag
            parsed = LanguageTag.parse(value)
        direct = self._definitions.get(str(parsed))
        if direct:
            return direct.tag
        base = self._aliases.get(parsed.language)
        if base is None:
            raise UnsupportedLanguageError("Language is not present in the registry")
        base_tag = self._definitions[base].tag
        return LanguageTag(base_tag.language, parsed.script, parsed.region or base_tag.region)

    def __contains__(self, value: object) -> bool:
        try:
            if not isinstance(value, (str, LanguageTag)):
                return False
            self.normalize(value)
        except (UnsupportedLanguageError, ValueError):
            return False
        return True

    def definitions(self) -> tuple[LanguageDefinition, ...]:
        return tuple(self._definitions.values())


def _definition(code: str, name: str, *aliases: str) -> LanguageDefinition:
    return LanguageDefinition(LanguageTag(code, region="IN"), name, frozenset(aliases))


DEFAULT_LANGUAGE_REGISTRY = LanguageRegistry(
    [
        _definition("en", "English"),
        _definition("as", "Assamese", "asm"),
        _definition("bn", "Bengali", "ben"),
        _definition("brx", "Bodo"),
        _definition("doi", "Dogri"),
        _definition("gu", "Gujarati", "guj"),
        _definition("hi", "Hindi", "hin"),
        _definition("kn", "Kannada", "kan"),
        _definition("ks", "Kashmiri", "kas"),
        _definition("kok", "Konkani"),
        _definition("mai", "Maithili"),
        _definition("ml", "Malayalam", "mal"),
        _definition("mni", "Manipuri"),
        _definition("mr", "Marathi", "mar"),
        _definition("ne", "Nepali", "nep"),
        _definition("or", "Odia", "od", "od-IN", "ory", "ori", "ori_Orya", "ory_Orya"),
        _definition("pa", "Punjabi", "pan"),
        _definition("sa", "Sanskrit", "san"),
        _definition("sat", "Santali"),
        _definition("sd", "Sindhi", "snd"),
        _definition("ta", "Tamil", "tam"),
        _definition("te", "Telugu", "tel"),
        _definition("ur", "Urdu", "urd"),
    ]
)
